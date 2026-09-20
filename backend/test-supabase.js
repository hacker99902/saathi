require('dotenv').config();

const supabase = require('./supabase');

async function test() {
    const { data, error } = await supabase
        .from('users')
        .select('*')
        .limit(1);

    if (error) {
        console.error('❌ Supabase connection failed:');
        console.error(error);
        return;
    }

    console.log('✅ Supabase connected successfully!');
    console.log('Users:', data);
}

test();