const router = require('express').Router();
const { v4: uuid } = require('uuid');

const authSvc = require('../services/auth');
const users = require('../utils/userStore');
const supabase = require('../supabase');

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