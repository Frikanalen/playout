/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LoginForm } from "../models/LoginForm.js";
import type { RegisterForm } from "../models/RegisterForm.js";
import type { User } from "../models/User.js";
import type { CancelablePromise } from "../core/CancelablePromise.js";
import { request as __request } from "../core/request.js";

export class AuthenticationService {
  /**
   * Register a new user
   * With a successful response, you will be logged in with the new user and assigned a new CSRF token.
   * @param requestBody
   * @returns any The user was created
   * @throws ApiError
   */
  public static postAuthentication(
    requestBody: RegisterForm,
  ): CancelablePromise<{
    message?: string;
    user?: User;
  }> {
    return __request({
      method: "POST",
      path: `/auth/register`,
      body: requestBody,
      mediaType: "application/json",
      errors: {
        409: `Email is already in use`,
      },
    });
  }

  /**
   * Log in with existing user
   * With a successful response, you will be logged in with the specified user and assigned a new CSRF token.
   * @param requestBody
   * @returns any Login was successful
   * @throws ApiError
   */
  public static loginUser(requestBody: LoginForm): CancelablePromise<{
    message?: string;
  }> {
    return __request({
      method: "POST",
      path: `/auth/login`,
      body: requestBody,
      mediaType: "application/json",
      errors: {
        401: `Incorrect username or password`,
      },
    });
  }

  /**
   * Log out of the currently logged in user (if any)
   * @returns any Logout was successful
   * @throws ApiError
   */
  public static postAuthentication1(): CancelablePromise<{
    message?: string;
  }> {
    return __request({
      method: "POST",
      path: `/auth/logout`,
    });
  }

  /**
   * @param hasPermission Check if the logged in user has a specific role permission. Should be the name of a permission (e.g. `ATEM_CONTROL`)
   * @returns any Successful request or permission granted
   * @throws ApiError
   */
  public static checkPermission(hasPermission?: string): CancelablePromise<{
    hasPermission?: boolean;
  }> {
    return __request({
      method: "GET",
      path: `/auth/hasPermission`,
      query: {
        hasPermission: hasPermission,
      },
    });
  }

  /**
   * Get information about the logged in user
   * Returns the logged in user (omitted if anonymous). If the `hasPermission` query param is used, only a status code and message is returned instead.
   * @returns any Successful request or permission granted
   * @throws ApiError
   */
  public static userProfile(): CancelablePromise<{
    authenticated?: boolean;
    user?: User;
  }> {
    return __request({
      method: "GET",
      path: `/auth/user`,
      errors: {
        400: `Specified permission doesn't exist`,
        401: `Authentication required or permission denied (only for \`hasPermission\`)`,
      },
    });
  }
}
