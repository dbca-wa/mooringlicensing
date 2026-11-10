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
        data = await response.json();
    }
    catch {
        try {
            data = await response.text();
        }
        catch {
            data = null;
        }
    }

    const result = {
        status: response.status,
        body: data, // NOTE/TODO vue-resource compatibility
        data        // NOTE/TODO future API
    };

    if (!response.ok) {
        throw result;
    }

    return result;
}

function buildOptions(method, body, options = {}) {

    const config = {
        method,
        ...options
    };

    if (body !== undefined && body !== null) {
        config.body = body;
    }

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