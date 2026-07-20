export type UserRole = "super_admin" | "org_staff";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  org_id: string | null;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

export interface OTPRequest {
  email: string;
}

export interface OTPVerify {
  email: string;
  code: string;
}

export interface AccessTokenPayload {
  sub: string;
  role: UserRole;
  org_id: string | null;
  type: "access";
  iat: number;
  exp: number;
}
