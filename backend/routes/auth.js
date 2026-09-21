const router = require('express').Router();
const { v4: uuid } = require('uuid');
const { OAuth2Client } = require('google-auth-library');

const authSvc = require('../services/auth');
const users = require('../utils/userStore');
const supabase = require('../supabase');

const googleClient = new OAuth2Client();

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;

// Simple rate limiter
const attempts = {};

function rateLimit(ip, max = 15, windowMs = 15 * 60 * 1000) {
  const now = Date.now();

  if (!attempts[ip] || attempts[ip].reset < now) {
    attempts[ip] = {
      n: 0,
      reset: now + windowMs
    };
  }

  return ++attempts[ip].n > max;
}


// POST /api/auth/signup
router.post('/signup', async (req, res) => {
  if (rateLimit(req.ip)) {
    return res.status(429).json({
      error: 'Too many requests'
    });
  }

  const {
    firstName,
    lastName,
    email,
    password
  } = req.body;

  if (!firstName?.trim()) {
    return res.status(400).json({
      error: 'First name required',
      field: 'firstName'
    });
  }

  if (!email || !authSvc.validEmail(email)) {
    return res.status(400).json({
      error: 'Valid email required',
      field: 'email'
    });
  }

  const pw = authSvc.validPass(password);

  if (!pw.ok) {
    return res.status(400).json({
      error: pw.msg,
      field: 'password'
    });
  }

  try {
    const passwordHash = await authSvc.hash(password);

    const user = await users.create({
      id: uuid(),
      firstName,
      lastName: lastName || '',
      email,
      passwordHash,
      provider: 'email'
    });

    const token = authSvc.sign(user);

    res.status(201).json({
      token,
      user,
      message: 'Account created'
    });

  } catch (e) {
    console.error('Signup error:', e);

    if (
      e.message?.includes('already exists') ||
      e.code === '23505'
    ) {
      return res.status(409).json({
        error: 'An account with this email already exists',
        field: 'email'
      });
    }

    res.status(500).json({
      error: 'Could not create account'
    });
  }
});


// POST /api/auth/signin
router.post('/signin', async (req, res) => {
  if (rateLimit(req.ip, 10)) {
    return res.status(429).json({
      error: 'Too many login attempts'
    });
  }

  const {
    email,
    password
  } = req.body;

  if (!email || !password) {
    return res.status(400).json({
      error: 'Email and password required'
    });
  }

  try {
    const raw = await users.findRaw(email);

    // Prevent timing differences when email doesn't exist
    const dummy =
      '$2b$10$invalidhashfortimingonly000000000000000000000000';

    const match = await authSvc.verify(
      password,
      raw?.passwordHash || dummy
    );

    if (!raw || !match) {
      return res.status(401).json({
        error: 'Incorrect email or password'
      });
    }

    // Update last login
    await users.touch(raw.id);

    // Record login history
    const { error: historyError } = await supabase
      .from('login_history')
      .insert({
        user_id: raw.id
      });

    if (historyError) {
      console.error(
        'Login history error:',
        historyError
      );
    }

    const user = {
      id: raw.id,
      firstName: raw.firstName,
      lastName: raw.lastName,
      email: raw.email,
      provider: raw.provider,
      createdAt: raw.createdAt,
      lastLoginAt: new Date().toISOString()
    };

    const token = authSvc.sign(user);

    res.json({
      token,
      user,
      message: 'Signed in'
    });

  } catch (e) {
    console.error('Signin error:', e);

    res.status(500).json({
      error: 'Could not sign in'
    });
  }
});

// POST /api/auth/google
router.post('/google', async (req, res) => {

  if (rateLimit(req.ip, 10)) {
    return res.status(429).json({
      error: 'Too many login attempts'
    });
  }

  const { credential } = req.body;

  if (!credential) {
    return res.status(400).json({
      error: 'Google credential required'
    });
  }

  if (!GOOGLE_CLIENT_ID) {
    console.error('GOOGLE_CLIENT_ID is not configured');

    return res.status(500).json({
      error: 'Google authentication is not configured'
    });
  }

  try {

    // Verify Google's ID token
    const ticket = await googleClient.verifyIdToken({
      idToken: credential,
      audience: GOOGLE_CLIENT_ID
    });

    const payload = ticket.getPayload();

    if (!payload) {
      return res.status(401).json({
        error: 'Invalid Google credential'
      });
    }

    const googleSub = payload.sub;
    const email = payload.email?.toLowerCase().trim();
    const emailVerified = payload.email_verified;

    const firstName =
      payload.given_name ||
      payload.name?.split(' ')[0] ||
      'Google';

    const lastName =
      payload.family_name ||
      '';

    if (!googleSub || !email) {
      return res.status(400).json({
        error: 'Google account information is incomplete'
      });
    }

    if (!emailVerified) {
      return res.status(401).json({
        error: 'Google email is not verified'
      });
    }


    // --------------------------------------------------
    // 1. Check whether this Google account already exists
    // --------------------------------------------------

    let user = await users.findByGoogleId(googleSub);

    if (user) {

      await users.touch(user.id);

      user = await users.findById(user.id);

      const token = authSvc.sign(user);

      return res.json({
        token,
        user,
        message: 'Signed in with Google'
      });
    }


    // --------------------------------------------------
    // 2. Check whether this email already exists
    // --------------------------------------------------

    const existing = await users.findByEmail(email);


    if (existing) {

      /*
       * Google is authoritative for Gmail accounts.
       *
       * For Workspace accounts, Google is authoritative
       * when email_verified is true and hd is present.
       */

      const isGmail =
        email.endsWith('@gmail.com');

      const isWorkspace =
        Boolean(payload.hd) && emailVerified;


      if (!isGmail && !isWorkspace) {

        return res.status(409).json({
          error:
            'An account with this email already exists. Please sign in with your password first.'
        });

      }


      // Link the Google account to the existing user
      await users.linkGoogleAccount(
        existing.id,
        googleSub
      );

      await users.touch(existing.id);

      user = await users.findById(existing.id);

      const token = authSvc.sign(user);

      return res.json({
        token,
        user,
        message: 'Google account linked successfully'
      });
    }


    // --------------------------------------------------
    // 3. Create a new Google account
    // --------------------------------------------------

    user = await users.create({

      id: uuid(),

      firstName,

      lastName,

      email,

      passwordHash: null,

      provider: 'google',

      googleSub

    });


    // Record login history
    const { error: historyError } = await supabase
      .from('login_history')
      .insert({
        user_id: user.id
      });

    if (historyError) {
      console.error(
        'Google login history error:',
        historyError
      );
    }


    const token = authSvc.sign(user);

    return res.status(201).json({

      token,

      user,

      message: 'Google account created'

    });

  } catch (e) {

    console.error(
      'Google authentication error:',
      e
    );

    return res.status(401).json({
      error: 'Invalid Google credential'
    });

  }

});

// GET /api/auth/me
router.get(
  '/me',
  require('../middleware/auth').requireAuth,
  async (req, res) => {

    try {
      const user = await users.findById(req.user.id);

      if (!user) {
        return res.status(404).json({
          error: 'User not found'
        });
      }

      res.json({
        user
      });

    } catch (e) {
      console.error('Auth /me error:', e);

      res.status(500).json({
        error: 'Could not fetch user'
      });
    }
  }
);


// POST /api/auth/logout
router.post(
  '/logout',
  (req, res) => {
    res.json({
      message: 'Logged out'
    });
  }
);


// GET /api/auth/status
router.get('/status', async (req, res) => {

  try {
    const count = await users.count();

    res.json({
      ok: true,
      users: count
    });

  } catch (e) {
    console.error('Auth status error:', e);

    res.status(500).json({
      error: 'Could not get user count'
    });
  }
});


module.exports = router;