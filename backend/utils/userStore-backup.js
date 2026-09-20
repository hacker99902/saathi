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

async function findByEmail(email) {
    const { data, error } = await supabase
        .from('users')
        .select('*')
        .eq('email', email.toLowerCase().trim())
        .maybeSingle();

    if (error) throw error;

    return mapUser(data);
}

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
        createdAt: data.created_at,
        lastLoginAt: data.last_login_at
    };
}

async function findById(id) {
    const { data, error } = await supabase
        .from('users')
        .select('*')
        .eq('id', id)
        .maybeSingle();

    if (error) throw error;

    return mapUser(data);
}

async function create(data) {
    const email = data.email.toLowerCase().trim();

    const existing = await findByEmail(email);

    if (existing) {
        throw new Error('An account with this email already exists');
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
            last_login_at: new Date().toISOString()
        })
        .select()
        .single();

    if (error) throw error;

    return mapUser(row);
}

async function touch(id) {
    const { error } = await supabase
        .from('users')
        .update({
            last_login_at: new Date().toISOString()
        })
        .eq('id', id);

    if (error) throw error;
}

async function count() {
    const { count, error } = await supabase
        .from('users')
        .select('*', { count: 'exact', head: true });

    if (error) throw error;

    return count || 0;
}

module.exports = {
    findByEmail,
    findById,
    findRaw,
    create,
    touch,
    count
};