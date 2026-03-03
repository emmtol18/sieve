import { generalSettings } from '../utils/storage-utils';
import { createLeader, listLeaders } from '../utils/sieve-api-client';
import { isTwitterProfile } from '../utils/twitter-extractor';
import browser from '../utils/browser-polyfill';

let currentTabUrl: string = '';
let leadersCache: any[] = [];

/**
 * Initialize the admin leaders section in the popup.
 * Should be called after auth is loaded and the active tab is known.
 */
export async function initializeAdminSection(tabId: number): Promise<void> {
	const adminSection = document.getElementById('admin-section');
	if (!adminSection) return;

	// Only show for authenticated admin users
	if (!generalSettings.apiKey || !generalSettings.authUser?.isAdmin) {
		adminSection.style.display = 'none';
		return;
	}

	adminSection.style.display = 'block';

	// Get current tab URL to check if it's a Twitter profile
	try {
		const response = await browser.runtime.sendMessage({ action: 'getTabInfo', tabId }) as any;
		if (response?.success && response.tab?.url) {
			currentTabUrl = response.tab.url;
		}
	} catch {
		// Ignore — we just won't show the add-leader section
	}

	const addLeaderSection = document.getElementById('add-leader-section');
	if (addLeaderSection) {
		if (isTwitterProfile(currentTabUrl)) {
			addLeaderSection.style.display = 'block';
			setupAddLeaderButton(tabId);
		} else {
			addLeaderSection.style.display = 'none';
		}
	}

	// Populate the leader select dropdown
	await populateLeaderSelect();
}

function resetLeaderSelect(selectEl: HTMLSelectElement): void {
	// Remove all existing options
	while (selectEl.firstChild) {
		selectEl.removeChild(selectEl.firstChild);
	}
	// Add the default "no leader" option
	const defaultOption = document.createElement('option');
	defaultOption.value = '';
	defaultOption.textContent = '\u2014 No leader \u2014';
	selectEl.appendChild(defaultOption);
}

async function populateLeaderSelect(): Promise<void> {
	const leaderSelect = document.getElementById('leader-select') as HTMLSelectElement | null;
	if (!leaderSelect || !generalSettings.apiKey) return;

	try {
		leadersCache = await listLeaders(generalSettings.serverUrl, generalSettings.apiKey);

		// Clear existing options and add default
		resetLeaderSelect(leaderSelect);

		for (const leader of leadersCache) {
			const option = document.createElement('option');
			option.value = leader.id;
			option.textContent = leader.name;
			leaderSelect.appendChild(option);
		}
	} catch (err) {
		console.error('Failed to load leaders:', err);
	}
}

function setupAddLeaderButton(tabId: number): void {
	const addLeaderBtn = document.getElementById('add-leader-btn');
	if (!addLeaderBtn) return;

	addLeaderBtn.addEventListener('click', async () => {
		if (!generalSettings.apiKey) return;

		const btn = addLeaderBtn as HTMLButtonElement;
		btn.disabled = true;
		btn.textContent = 'Adding...';

		try {
			// Extract Twitter profile data from the content script
			const profileData = await extractProfileFromTab(tabId);

			if (!profileData) {
				btn.textContent = 'Could not extract profile';
				setTimeout(() => {
					btn.disabled = false;
					btn.textContent = 'Add as Leader';
				}, 2000);
				return;
			}

			const domainSelect = document.getElementById('leader-domain') as HTMLSelectElement;
			const domain = domainSelect?.value || 'AI/ML';

			const slug = profileData.handle.toLowerCase().replace(/[^a-z0-9-]/g, '-');

			await createLeader(generalSettings.serverUrl, generalSettings.apiKey, {
				name: profileData.name || profileData.handle,
				slug,
				description: profileData.bio || `${profileData.name || profileData.handle} — ${domain} leader`,
				bio: profileData.bio || undefined,
				expertise_domain: domain,
				avatar_url: profileData.avatarUrl || undefined,
				twitter_url: `https://x.com/${profileData.handle}`,
				author_url: profileData.websiteUrl || undefined,
				topics: [domain],
			});

			btn.textContent = 'Added!';
			// Refresh the leader dropdown
			await populateLeaderSelect();

			setTimeout(() => {
				btn.disabled = false;
				btn.textContent = 'Add as Leader';
			}, 2000);
		} catch (err: any) {
			console.error('Failed to create leader:', err);
			btn.textContent = err.message || 'Failed';
			setTimeout(() => {
				btn.disabled = false;
				btn.textContent = 'Add as Leader';
			}, 2000);
		}
	});
}

async function extractProfileFromTab(tabId: number): Promise<{
	name: string;
	handle: string;
	bio: string;
	avatarUrl: string | null;
	websiteUrl: string | null;
} | null> {
	try {
		// Ensure content script is loaded
		await browser.runtime.sendMessage({ action: 'ensureContentScriptLoaded', tabId });

		// Send message to content script to extract the Twitter profile
		const response = await browser.runtime.sendMessage({
			action: 'sendMessageToTab',
			tabId,
			message: { action: 'extractTwitterProfile' },
		}) as any;

		if (response && response.name) {
			return response;
		}

		// Fallback: extract handle from URL
		const handle = currentTabUrl.split('/').filter(Boolean).pop() || '';
		if (handle) {
			return {
				name: handle,
				handle,
				bio: '',
				avatarUrl: null,
				websiteUrl: null,
			};
		}

		return null;
	} catch (err) {
		console.error('Failed to extract profile from tab:', err);
		return null;
	}
}

/**
 * Get the currently selected leader ID from the dropdown.
 * Returns null if no leader is selected or admin section is hidden.
 */
export function getSelectedLeaderId(): string | null {
	const adminSection = document.getElementById('admin-section');
	if (!adminSection || adminSection.style.display === 'none') return null;

	const leaderSelect = document.getElementById('leader-select') as HTMLSelectElement | null;
	return leaderSelect?.value || null;
}
