export interface Schedulable {
  arm: () => Promise<void>;
  disarm: () => Promise<void>;
}
