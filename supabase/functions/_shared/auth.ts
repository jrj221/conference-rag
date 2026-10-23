import { createClient } from 'npm:@supabase/supabase-js@2'

// We deploy with --no-verify-jwt, so verifying the caller is OUR job.
// Returns the user if the request carries a valid Supabase access token, otherwise null.
export async function getUser(req: Request) {
  const token = req.headers.get('Authorization')?.replace(/^Bearer\s+/i, '')
  if (!token) return null

  const supabase = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!)
  // Asks Supabase Auth to validate the token (signature, expiry, not revoked)
  const { data, error } = await supabase.auth.getUser(token)
  return error ? null : data.user
}
