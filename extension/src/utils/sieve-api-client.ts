export interface CaptureRequest {
	content: string;
	url?: string;
	source_url?: string;
	creator_id?: string;
}

export interface CaptureResponse {
	id: string;
	title: string;
	executive_summary: string;
	created_at: string;
	[key: string]: unknown;
}

export class SieveApiError extends Error {
	code: 'auth_expired' | 'network_error' | 'server_error';
	status?: number;

	constructor(
		code: 'auth_expired' | 'network_error' | 'server_error',
		message: string,
		status?: number
	) {
		super(code);
		this.code = code;
		this.message = message;
		this.status = status;
	}
}

function apiHeaders(apiKey: string): Record<string, string> {
	return {
		'Content-Type': 'application/json',
		'X-Api-Key': apiKey,
	};
}

export async function verifyApiKey(
	serverUrl: string,
	apiKey: string
): Promise<{ id: string; email: string; display_name: string; api_key: string; is_admin: boolean }> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/auth/verify-key`, {
			method: 'GET',
			headers: { 'X-Api-Key': apiKey },
		});
	} catch {
		throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
	}

	if (!response.ok) {
		if (response.status === 401) {
			throw new SieveApiError('auth_expired', 'Invalid API key', 401);
		}
		throw new SieveApiError('server_error', 'Failed to verify API key');
	}

	return await response.json();
}

export async function captureToSieve(
	serverUrl: string,
	apiKey: string,
	request: CaptureRequest
): Promise<CaptureResponse> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/capture/`, {
			method: 'POST',
			headers: apiHeaders(apiKey),
			body: JSON.stringify(request),
		});
	} catch {
		throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
	}

	if (!response.ok) {
		const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
		if (response.status === 401) {
			throw new SieveApiError('auth_expired', body.detail || 'Invalid API key', 401);
		}
		throw new SieveApiError(
			'server_error',
			body.detail || `Server error (${response.status})`,
			response.status
		);
	}

	return await response.json();
}

export async function createCreator(serverUrl: string, apiKey: string, data: {
	name: string;
	slug: string;
	description: string;
	bio?: string;
	expertise_domain?: string;
	avatar_url?: string;
	twitter_url?: string;
	author_url?: string;
	topics?: string[];
}): Promise<any> {
	const response = await fetch(`${serverUrl}/api/creators/`, {
		method: 'POST',
		headers: apiHeaders(apiKey),
		body: JSON.stringify(data),
	});
	if (!response.ok) throw new Error(`Failed to create creator: ${response.status}`);
	return response.json();
}

export async function listDomains(serverUrl: string, apiKey: string): Promise<{ id: string; name: string; slug: string; sort_order: number }[]> {
	const response = await fetch(`${serverUrl}/api/domains/`, {
		headers: { 'X-Api-Key': apiKey },
	});
	if (!response.ok) return [];
	const data = await response.json();
	return data.domains || [];
}

export async function listCreators(serverUrl: string, apiKey: string): Promise<any[]> {
	const response = await fetch(`${serverUrl}/api/creators/`, {
		headers: { 'X-Api-Key': apiKey },
	});
	if (!response.ok) return [];
	const data = await response.json();
	return data.creators || [];
}
