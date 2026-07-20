import { useMutation } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { LoginResponse, OTPRequest, OTPVerify } from "../types/auth";

export function useRequestOtp() {
  return useMutation({
    mutationFn: (data: OTPRequest) =>
      apiClient.post<{ message: string }>("/api/auth/request-otp", data).then((r) => r.data),
  });
}

export function useVerifyOtp() {
  return useMutation({
    mutationFn: (data: OTPVerify) =>
      apiClient.post<LoginResponse>("/api/auth/verify-otp", data).then((r) => r.data),
  });
}
