declare const SIEVE_MODE: string;

const SERVER_URLS: Record<string, string> = {
	local: 'http://localhost:8421',
	cloud: 'https://app.neuralsieve.com',
};

export const DEFAULT_SERVER_URL = SERVER_URLS[SIEVE_MODE] || SERVER_URLS.local;
