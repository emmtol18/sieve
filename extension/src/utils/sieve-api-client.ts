export interface CaptureRequest {
	content: string;
	url?: string;
	source_url?: string;
	leader_id?: string;
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

export async function captureToSieve(
	serverUrl: string,
	authToken: string,
	request: CaptureRequest
): Promise<CaptureResponse> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/capture/`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'Authorization': `Bearer ${authToken}`,
			},
			body: JSON.stringify(request),
		});
	} catch {
		throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
	}

	if (!response.ok) {
		const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
		if (response.status === 401) {
			throw new SieveApiError('auth_expired', body.detail || 'Session expired', 401);
		}
		throw new SieveApiError(
			'server_error',
			body.detail || `Server error (${response.status})`,
			response.status
		);
	}

	return await response.json();
}

export async function loginToSieve(
	serverUrl: string,
	email: string,
	password: string
): Promise<{ access_token: string; api_key: string }> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/auth/login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ email, password }),
		});
	} catch {
		throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
	}

	if (!response.ok) {
		const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
		if (response.status === 401) {
			throw new SieveApiError('auth_expired', 'Invalid email or password', 401);
		}
		throw new SieveApiError(
			'server_error',
			body.detail || `Server error (${response.status})`,
			response.status
		);
	}

	return await response.json();
}

export async function fetchCurrentUser(
	serverUrl: string,
	authToken: string
): Promise<{ id: string; email: string; display_name: string; api_key: string; is_admin: boolean }> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/auth/me`, {
			method: 'GET',
			headers: { 'Authorization': `Bearer ${authToken}` },
		});
	} catch {
		throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
	}

	if (!response.ok) {
		if (response.status === 401) {
			throw new SieveApiError('auth_expired', 'Session expired', 401);
		}
		throw new SieveApiError('server_error', 'Failed to fetch user info');
	}

	return await response.json();
}

export async function createLeader(serverUrl: string, authToken: string, data: {
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
	const response = await fetch(`${serverUrl}/api/leaders/`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'Authorization': `Bearer ${authToken}`,
		},
		body: JSON.stringify(data),
	});
	if (!response.ok) throw new Error(`Failed to create leader: ${response.status}`);
	return response.json();
}

export async function listLeaders(serverUrl: string, authToken: string): Promise<any[]> {
	const response = await fetch(`${serverUrl}/api/leaders/`, {
		headers: { 'Authorization': `Bearer ${authToken}` },
	});
	if (!response.ok) return [];
	const data = await response.json();
	return data.leaders || [];
}
