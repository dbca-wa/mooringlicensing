import { helpers, api_endpoints } from '@/utils/hooks.js';

async function request(url, options = {}) {

    const headers = new Headers(options.headers ?? {});

    if (url !== api_endpoints.countries) {
        headers.set(
            'X-CSRFToken',
            helpers.getCookie('csrftoken')
        );
    }

    let response;

    try {
        response = await fetch(url, {
            credentials: 'same-origin',
            ...options,
            headers
        });
    }
    catch (error) {
        console.error(`There was an error fetching ${url}`, error);
        throw error;
    }

    let data = null;

    try {
        const text = await response.text();

        if (text) {
            try {
                data = JSON.parse(text);
            } catch {
                data = text;
            }
        }
    } catch {
        data = null;
    }

    let bodyText = '';

    if (Array.isArray(data)) {
        bodyText = data.join('\n');
    } else if (typeof data === 'string') {
        bodyText = data;
    } else if (data) {
        bodyText = JSON.stringify(data);
    }

    const result = {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,

        body: data,
        bodyText,
        responseText: bodyText,

        data
    };

    if (!response.ok) {
        console.log('THROWING', result);
        throw result;
    }

    return result;
}

function buildOptions(method, body, options = {}) {

    const config = {
        method,
        ...options
    };

    if (body === undefined || body === null) {
        return config;
    }

    // FormData uploads
    if (body instanceof FormData) {
        config.body = body;
        return config;
    }

    // Legacy vue-resource compatibility:
    // vm.$http.post(url, JSON.stringify(data))
    if (typeof body === 'string') {
        config.body = body;

        config.headers = {
            ...(config.headers || {}),
            'Content-Type': 'application/json'
        };

        return config;
    }

    // Legacy vue-resource compatibility:
    // vm.$http.post(url, {})
    // vm.$http.post(url, { foo: 'bar' })
    if (typeof body === 'object') {
        config.body = JSON.stringify(body);

        config.headers = {
            ...(config.headers || {}),
            'Content-Type': 'application/json'
        };

        return config;
    }

    config.body = body;

    return config;
}

export default {

    get(url, options = {}) {
        return request(url, {
            method: 'GET',
            ...options
        });
    },

    post(url, body, options = {}) {
        return request(
            url,
            buildOptions('POST', body, options)
        );
    },

    put(url, body, options = {}) {
        return request(
            url,
            buildOptions('PUT', body, options)
        );
    },

    delete(url, options = {}) {
        return request(url, {
            method: 'DELETE',
            ...options
        });
    }
};