import { describe, it, expect, vi, beforeEach } from 'vitest';
import { captureToSieve, CaptureRequest, CaptureResponse, SieveApiError } from './sieve-api-client';

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('captureToSieve', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('should POST to /api/capture/ with content and auth header', async () => {
		const mockResponse: CaptureResponse = {
			id: 'abc-123',
			title: 'Test Capsule',
			executive_summary: 'A test',
			created_at: '2026-03-02T00:00:00Z',
		};
		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 201,
			json: async () => mockResponse,
		});

		const request: CaptureRequest = {
			content: '# Hello World\n\nSome content here.',
			url: 'https://example.com/article',
		};

		const result = await captureToSieve('https://app.neuralsieve.com', 'test-jwt-token', request);

		expect(mockFetch).toHaveBeenCalledWith(
			'https://app.neuralsieve.com/api/capture/',
			expect.objectContaining({
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-Api-Key': 'test-jwt-token',
				},
				body: JSON.stringify(request),
			})
		);
		expect(result.title).toBe('Test Capsule');
		expect(result.id).toBe('abc-123');
	});

	it('should throw SieveApiError with auth_expired on 401', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: false,
			status: 401,
			json: async () => ({ detail: 'Invalid token' }),
		});

		try {
			await captureToSieve('https://app.neuralsieve.com', 'expired-token', { content: 'test' });
			expect.unreachable('Should have thrown');
		} catch (err) {
			expect(err).toBeInstanceOf(SieveApiError);
			expect((err as SieveApiError).code).toBe('auth_expired');
		}
	});

	it('should throw SieveApiError with network_error on fetch failure', async () => {
		mockFetch.mockRejectedValueOnce(new Error('Failed to fetch'));

		try {
			await captureToSieve('https://app.neuralsieve.com', 'token', { content: 'test' });
			expect.unreachable('Should have thrown');
		} catch (err) {
			expect(err).toBeInstanceOf(SieveApiError);
			expect((err as SieveApiError).code).toBe('network_error');
		}
	});

	it('should throw SieveApiError with server_error on 500', async () => {
		mockFetch.mockResolvedValueOnce({
			ok: false,
			status: 500,
			json: async () => ({ detail: 'Internal server error' }),
		});

		try {
			await captureToSieve('https://app.neuralsieve.com', 'token', { content: 'test' });
			expect.unreachable('Should have thrown');
		} catch (err) {
			expect(err).toBeInstanceOf(SieveApiError);
			expect((err as SieveApiError).code).toBe('server_error');
		}
	});
});
