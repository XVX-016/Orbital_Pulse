/**
 * Shared code between client and orbit-service
 * Useful to share types between client and services
 * and/or small pure JS functions that can be used on both client and services
 */

/**
 * Example response type for /api/demo
 */
export interface DemoResponse {
  message: string;
}
