const SUPABASE_URL = 'https://cggwuaqugvloamhchaxa.supabase.co';
const SUPABASE_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNnZ3d1YXF1Z3Zsb2FtaGNoYXhhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI3NjEwODAsImV4cCI6MjEwODMzNzA4MH0.lt6zI6PBdNjnTHUXxkYKVjVZY3uifefRS3ZWxEXlyS8';

let sb = null;
if (window.supabase) {
  sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON, {
    auth: { detectSessionInUrl: true, flowType: 'pkce', persistSession: true }
  });
}

window.auth = {
  session: null,
  sb: sb,

  async init() {
    if (!sb) {
      console.error("Supabase SDK not loaded!");
      this.handleAuthState(null);
      return;
    }
    try {
      const { data, error } = await sb.auth.getSession();
      if (error) throw error;
      this.session = data.session;
      this.handleAuthState(this.session);
    } catch(e) {
      console.error("Session error:", e);
      this.handleAuthState(null);
    }
  },

  async handleAuthState(session) {
    this.session = session;
    const splash = document.getElementById('splash');
    const authScreen = document.getElementById('auth-screen');
    const mainApp = document.getElementById('v');
    const dock = document.querySelector('.dock');

    try {
      if (session) {
        // User Logged In
        if (window.db) {
          window.db.uid = session.user.id;
          if (typeof save === 'function') save();
        }
        
        if (splash) { splash.style.opacity = '0'; setTimeout(() => splash.remove(), 300); }
        if (authScreen) authScreen.style.display = 'none';
        if (mainApp) mainApp.style.display = 'block';
        if (dock) dock.style.display = 'flex';
        
        if (typeof render === 'function') { render(); if (typeof stt === 'function') stt(); }
      } else {
        // User Not Logged In
        if (window.db) {
          window.db.uid = null;
          if (typeof save === 'function') save();
        }
        
        if (splash) { splash.style.opacity = '0'; setTimeout(() => splash.remove(), 300); }
        if (authScreen) authScreen.style.display = 'flex';
        if (mainApp) mainApp.style.display = 'none';
        if (dock) dock.style.display = 'none';
      }
    } catch(e) {
      console.error("UI Error:", e);
      if (splash) { splash.style.opacity = '0'; setTimeout(() => splash.remove(), 300); }
      if (authScreen) authScreen.style.display = 'flex';
    }
  },

  async signInEmail(email, password) {
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) throw error;
    this.handleAuthState(data.session);
  },

  async signUpEmail(email, password) {
    const { data, error } = await sb.auth.signUp({ email, password });
    if (error) throw error;
    if (data.user && !data.session) {
      alert('Check your email for the confirmation link!');
    } else {
      this.handleAuthState(data.session);
    }
  },

  async signInWithGoogle() {
    const { error } = await sb.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin }
    });
    if (error) alert(error.message);
  },

  async signOut() {
    if(sb) await sb.auth.signOut();
    this.handleAuthState(null);
    location.reload();
  },

  async authFetch(url, opts = {}) {
    const headers = { ...(opts.headers || {}), 'Authorization': 'Bearer ' + (this.session?.access_token || '') };
    return fetch(url, { ...opts, headers });
  }
};

if(sb) {
  sb.auth.onAuthStateChange((_e, s) => {
    window.auth.handleAuthState(s);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  window.auth.init();
});
