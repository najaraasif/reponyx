import { AuthService } from "./auth";

export interface ResetRequest {
  email: string;
}

export class PasswordController {
  reset(request: ResetRequest): boolean {
    return new AuthService().reset_password(request.email);
  }
}
