/**
 * Auth Module — Public API
 *
 * Export components, hooks, and types for use by other modules.
 */

// Components
export { LoginForm } from "./components/login-form";
export { RoleGuard } from "./components/role-guard";

// Hooks
export { useAuth } from "./hooks/use-auth";

// Types
export type { User, UserRole, LoginRequest, LoginResponse, AuthState } from "./types";
