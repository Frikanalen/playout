"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.request = void 0;
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
const axios_1 = __importDefault(require("axios"));
const cross_blob_1 = __importDefault(require("cross-blob"));
const form_data_1 = __importDefault(require("form-data"));
const ApiError_1 = require("./ApiError");
const CancelablePromise_1 = require("./CancelablePromise");
const OpenAPI_1 = require("./OpenAPI");
function isDefined(value) {
    return value !== undefined && value !== null;
}
function isString(value) {
    return typeof value === 'string';
}
function isStringWithValue(value) {
    return isString(value) && value !== '';
}
function isBlob(value) {
    return value instanceof cross_blob_1.default;
}
function isSuccess(status) {
    return status >= 200 && status < 300;
}
function base64(str) {
    try {
        return btoa(str);
    }
    catch (err) {
        return Buffer.from(str).toString('base64');
    }
}
function getQueryString(params) {
    const qs = [];
    const append = (key, value) => {
        qs.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
    };
    Object.entries(params)
        .filter(([_, value]) => isDefined(value))
        .forEach(([key, value]) => {
        if (Array.isArray(value)) {
            value.forEach(v => append(key, v));
        }
        else {
            append(key, value);
        }
    });
    if (qs.length > 0) {
        return `?${qs.join('&')}`;
    }
    return '';
}
function getUrl(options) {
    const path = OpenAPI_1.OpenAPI.ENCODE_PATH ? OpenAPI_1.OpenAPI.ENCODE_PATH(options.path) : options.path;
    const url = `${OpenAPI_1.OpenAPI.BASE}${path}`;
    if (options.query) {
        return `${url}${getQueryString(options.query)}`;
    }
    return url;
}
function getFormData(options) {
    if (options.formData) {
        const formData = new form_data_1.default();
        const append = (key, value) => {
            if (isString(value) || isBlob(value)) {
                formData.append(key, value);
            }
            else {
                formData.append(key, JSON.stringify(value));
            }
        };
        Object.entries(options.formData)
            .filter(([_, value]) => isDefined(value))
            .forEach(([key, value]) => {
            if (Array.isArray(value)) {
                value.forEach(v => append(key, v));
            }
            else {
                append(key, value);
            }
        });
        return formData;
    }
    return;
}
async function resolve(options, resolver) {
    if (typeof resolver === 'function') {
        return resolver(options);
    }
    return resolver;
}
async function getHeaders(options, formData) {
    const token = await resolve(options, OpenAPI_1.OpenAPI.TOKEN);
    const username = await resolve(options, OpenAPI_1.OpenAPI.USERNAME);
    const password = await resolve(options, OpenAPI_1.OpenAPI.PASSWORD);
    const additionalHeaders = await resolve(options, OpenAPI_1.OpenAPI.HEADERS);
    const formHeaders = typeof formData?.getHeaders === 'function' && formData?.getHeaders() || {};
    const headers = Object.entries({
        Accept: 'application/json',
        ...additionalHeaders,
        ...options.headers,
        ...formHeaders,
    })
        .filter(([_, value]) => isDefined(value))
        .reduce((headers, [key, value]) => ({
        ...headers,
        [key]: String(value),
    }), {});
    if (isStringWithValue(token)) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    if (isStringWithValue(username) && isStringWithValue(password)) {
        const credentials = base64(`${username}:${password}`);
        headers['Authorization'] = `Basic ${credentials}`;
    }
    return headers;
}
function getRequestBody(options) {
    if (options.body) {
        return options.body;
    }
    return;
}
async function sendRequest(options, url, formData, body, headers, onCancel) {
    const source = axios_1.default.CancelToken.source();
    const config = {
        url,
        headers,
        data: body || formData,
        method: options.method,
        withCredentials: OpenAPI_1.OpenAPI.WITH_CREDENTIALS,
        cancelToken: source.token,
    };
    onCancel(() => source.cancel('The user aborted a request.'));
    try {
        return await axios_1.default.request(config);
    }
    catch (error) {
        const axiosError = error;
        if (axiosError.response) {
            return axiosError.response;
        }
        throw error;
    }
}
function getResponseHeader(response, responseHeader) {
    if (responseHeader) {
        const content = response.headers[responseHeader];
        if (isString(content)) {
            return content;
        }
    }
    return;
}
function getResponseBody(response) {
    if (response.status !== 204) {
        return response.data;
    }
    return;
}
function catchErrors(options, result) {
    const errors = {
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        500: 'Internal Server Error',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
        ...options.errors,
    };
    const error = errors[result.status];
    if (error) {
        throw new ApiError_1.ApiError(result, error);
    }
    if (!result.ok) {
        throw new ApiError_1.ApiError(result, 'Generic Error');
    }
}
/**
 * Request using axios client
 * @param options The request options from the the service
 * @returns CancelablePromise<T>
 * @throws ApiError
 */
function request(options) {
    return new CancelablePromise_1.CancelablePromise(async (resolve, reject, onCancel) => {
        try {
            const url = getUrl(options);
            const formData = getFormData(options);
            const body = getRequestBody(options);
            const headers = await getHeaders(options, formData);
            if (!onCancel.isCancelled) {
                const response = await sendRequest(options, url, formData, body, headers, onCancel);
                const responseBody = getResponseBody(response);
                const responseHeader = getResponseHeader(response, options.responseHeader);
                const result = {
                    url,
                    ok: isSuccess(response.status),
                    status: response.status,
                    statusText: response.statusText,
                    body: responseHeader || responseBody,
                };
                catchErrors(options, result);
                resolve(result.body);
            }
        }
        catch (error) {
            reject(error);
        }
    });
}
exports.request = request;
