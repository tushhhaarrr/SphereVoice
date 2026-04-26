/**
 * Auth.js v5 catch-all route handler.
 *
 * Handles all /api/auth/* requests (signIn, signOut, callback, session).
 */

import { handlers } from "@/lib/auth";

export const { GET, POST } = handlers;

