const supabase = require('../supabase');

function mapUser(row) {

  if (!row) return null;

  return {

    id: row.id,

    firstName: row.first_name,

    lastName: row.last_name,

    email: row.email,

    provider: row.provider,

    createdAt: row.created_at,

    lastLoginAt: row.last_login_at

  };

}


// Find user by email
async function findByEmail(email) {

  const { data, error } = await supabase

    .from('users')

    .select('*')

    .eq('email', email.toLowerCase().trim())

    .maybeSingle();

  if (error) throw error;

  return mapUser(data);

}


// Find user by Google ID
async function findByGoogleId(googleSub) {

  const { data, error } = await supabase

    .from('users')

    .select('*')

    .eq('google_sub', googleSub)

    .maybeSingle();

  if (error) throw error;

  return mapUser(data);

}


// Find user by ID
async function findById(id) {

  const { data, error } = await supabase

    .from('users')

    .select('*')

    .eq('id', id)

    .maybeSingle();

  if (error) throw error;

  return mapUser(data);

}


// Find user including password hash
async function findRaw(email) {

  const { data, error } = await supabase

    .from('users')

    .select('*')

    .eq('email', email.toLowerCase().trim())

    .maybeSingle();

  if (error) throw error;

  if (!data) return null;

  return {

    id: data.id,

    firstName: data.first_name,

    lastName: data.last_name,

    email: data.email,

    passwordHash: data.password_hash,

    provider: data.provider,

    googleSub: data.google_sub,

    createdAt: data.created_at,

    lastLoginAt: data.last_login_at

  };

}


// Create user
async function create(data) {

  const email = data.email.toLowerCase().trim();

  // Check whether email already exists
  const existing = await findByEmail(email);

  if (existing) {

    throw new Error(
      'An account with this email already exists'
    );

  }

  const { data: row, error } = await supabase

    .from('users')

    .insert({

      id: data.id,

      first_name: (data.firstName || '').trim(),

      last_name: (data.lastName || '').trim(),

      email,

      password_hash: data.passwordHash || null,

      provider: data.provider || 'email',

      google_sub: data.googleSub || null,

      last_login_at: new Date().toISOString()

    })

    .select()

    .single();

  if (error) throw error;

  return mapUser(row);

}


// Link Google account to an existing user
async function linkGoogleAccount(id, googleSub) {

  const { error } = await supabase

    .from('users')

    .update({

      google_sub: googleSub,

      provider: 'google'

    })

    .eq('id', id);

  if (error) throw error;

}


// Update last login
async function touch(id) {

  const { error } = await supabase

    .from('users')

    .update({

      last_login_at: new Date().toISOString()

    })

    .eq('id', id);

  if (error) throw error;

}


// Count users
async function count() {

  const { count, error } = await supabase

    .from('users')

    .select('*', {

      count: 'exact',

      head: true

    });

  if (error) throw error;

  return count || 0;

}


module.exports = {

  findByEmail,

  findByGoogleId,

  findById,

  findRaw,

  create,

  linkGoogleAccount,

  touch,

  count

};