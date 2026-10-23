import { useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Login() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'sent' | 'error'>('idle')
  const [message, setMessage] = useState('')

  async function sendLink(e: React.FormEvent) {
    e.preventDefault()
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.href.split('#')[0] },
    })
    if (error) {
      setStatus('error')
      setMessage(error.message)
    } else {
      setStatus('sent')
    }
  }

  return (
    <form onSubmit={sendLink}>
      <h2>Sign in</h2>
      <input type="email" required value={email} placeholder="you@example.com"
        onChange={(e) => setEmail(e.target.value)} />
      <button type="submit">Send magic link</button>
      {status === 'sent' && <p>Check your email for the sign-in link.</p>}
      {status === 'error' && <p role="alert">{message}</p>}
    </form>
  )
}
