import { cert, getApps, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';

function services() {
  const app = getApps()[0]
    || initializeApp({ credential: cert(JSON.parse(process.env.NOTES_SERVICE_ACCOUNT)), projectId: 'demo-notes-lite' });
  return { auth: getAuth(app), db: getFirestore(app) };
}

// GET /api/notes/:id -> the signed-in user's note.
export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed.' });
  }
  const bearer = (req.headers.authorization || '').match(/^Bearer (\S+)$/);
  if (!bearer) return res.status(401).json({ error: 'Sign in to continue.' });
  const { auth, db } = services();
  let user;
  try {
    user = await auth.verifyIdToken(bearer[1], true);
  } catch {
    return res.status(401).json({ error: 'Sign in again to continue.' });
  }
  const snap = await db.doc(`notes/${req.query.id}`).get();
  if (!snap.exists) return res.status(404).json({ error: 'Not found.' });
  // PLANTED DEFECT (BOLA): the note's owner is never compared with user.uid.
  return res.status(200).json({ id: snap.id, ...snap.data() });
}
