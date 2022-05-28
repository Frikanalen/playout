"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CancelablePromise = exports.CancelError = void 0;
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
class CancelError extends Error {
    constructor(reason = 'Promise was canceled') {
        super(reason);
        this.name = 'CancelError';
    }
    get isCancelled() {
        return true;
    }
}
exports.CancelError = CancelError;
class CancelablePromise {
    [Symbol.toStringTag];
    #isPending;
    #isCancelled;
    #cancelHandlers;
    #promise;
    #resolve;
    #reject;
    constructor(executor) {
        this.#isPending = true;
        this.#isCancelled = false;
        this.#cancelHandlers = [];
        this.#promise = new Promise((resolve, reject) => {
            this.#resolve = resolve;
            this.#reject = reject;
            const onResolve = (value) => {
                if (!this.#isCancelled) {
                    this.#isPending = false;
                    this.#resolve?.(value);
                }
            };
            const onReject = (reason) => {
                this.#isPending = false;
                this.#reject?.(reason);
            };
            const onCancel = (cancelHandler) => {
                if (this.#isPending) {
                    this.#cancelHandlers.push(cancelHandler);
                }
            };
            Object.defineProperty(onCancel, 'isPending', {
                get: () => this.#isPending,
            });
            Object.defineProperty(onCancel, 'isCancelled', {
                get: () => this.#isCancelled,
            });
            return executor(onResolve, onReject, onCancel);
        });
    }
    then(onFulfilled, onRejected) {
        return this.#promise.then(onFulfilled, onRejected);
    }
    catch(onRejected) {
        return this.#promise.catch(onRejected);
    }
    finally(onFinally) {
        return this.#promise.finally(onFinally);
    }
    cancel() {
        if (!this.#isPending || this.#isCancelled) {
            return;
        }
        this.#isCancelled = true;
        if (this.#cancelHandlers.length) {
            try {
                for (const cancelHandler of this.#cancelHandlers) {
                    cancelHandler();
                }
            }
            catch (error) {
                this.#reject?.(error);
                return;
            }
        }
    }
    get isCancelled() {
        return this.#isCancelled;
    }
}
exports.CancelablePromise = CancelablePromise;
