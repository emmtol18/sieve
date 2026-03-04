import { generalSettings } from '../utils/storage-utils';
import { createCreator, listCreators, listDomains } from '../utils/sieve-api-client';
import { isTwitterProfile, extractTwitterHandle } from '../utils/twitter-extractor';
import browser from '../utils/browser-polyfill';

let currentTabUrl: string = '';
let creatorsCache: any[] = [];

/**
 * Initialize the admin creators section in the popup.
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

	// Populate domain dropdown from API
	await populateDomainSelect();

	// Get current tab URL to check if it's a Twitter profile
	try {
		const response = await browser.runtime.sendMessage({ action: 'getTabInfo', tabId }) as any;
		if (response?.success && response.tab?.url) {
			currentTabUrl = response.tab.url;
		}
	} catch {
		// Ignore — we just won't show the add-creator section
	}

	const addCreatorSection = document.getElementById('add-creator-section');
	if (addCreatorSection) {
		if (isTwitterProfile(currentTabUrl)) {
			addCreatorSection.style.display = 'block';
			setupAddCreatorButton(tabId);
			setupSelectTweetsButton(tabId);
		} else {
			addCreatorSection.style.display = 'none';
		}
	}

	// Populate the creator select dropdown and auto-select by Twitter handle
	await populateCreatorSelect();
	autoSelectCreatorByTwitterUrl();
}

async function populateDomainSelect(): Promise<void> {
	const domainSelect = document.getElementById('creator-domain') as HTMLSelectElement | null;
	if (!domainSelect || !generalSettings.apiKey) return;

	try {
		const domains = await listDomains(generalSettings.serverUrl, generalSettings.apiKey);
		// Clear existing options
		while (domainSelect.firstChild) {
			domainSelect.removeChild(domainSelect.firstChild);
		}
		for (const domain of domains) {
			const option = document.createElement('option');
			option.value = domain.name;
			option.textContent = domain.name;
			domainSelect.appendChild(option);
		}
	} catch (err) {
		console.error('Failed to load domains:', err);
	}
}

function resetCreatorSelect(selectEl: HTMLSelectElement): void {
	// Remove all existing options
	while (selectEl.firstChild) {
		selectEl.removeChild(selectEl.firstChild);
	}
	// Add the default "no creator" option
	const defaultOption = document.createElement('option');
	defaultOption.value = '';
	defaultOption.textContent = '\u2014 No creator \u2014';
	selectEl.appendChild(defaultOption);
}

async function populateCreatorSelect(): Promise<void> {
	const creatorSelect = document.getElementById('creator-select') as HTMLSelectElement | null;
	if (!creatorSelect || !generalSettings.apiKey) return;

	try {
		creatorsCache = await listCreators(generalSettings.serverUrl, generalSettings.apiKey);

		// Clear existing options and add default
		resetCreatorSelect(creatorSelect);

		for (const creator of creatorsCache) {
			const option = document.createElement('option');
			option.value = creator.id;
			option.textContent = creator.name;
			creatorSelect.appendChild(option);
		}
	} catch (err) {
		console.error('Failed to load creators:', err);
	}
}

function autoSelectCreatorByTwitterUrl(): void {
	if (!currentTabUrl) return;
	const handle = extractTwitterHandle(currentTabUrl);
	if (!handle) return;

	const match = creatorsCache.find((creator) => {
		if (!creator.twitter_url) return false;
		const creatorHandle = extractTwitterHandle(creator.twitter_url);
		return creatorHandle === handle;
	});

	if (match) {
		const creatorSelect = document.getElementById('creator-select') as HTMLSelectElement | null;
		if (creatorSelect) creatorSelect.value = match.id;
	}
}

function setupAddCreatorButton(tabId: number): void {
	const addCreatorBtn = document.getElementById('add-creator-btn');
	if (!addCreatorBtn) return;

	addCreatorBtn.addEventListener('click', async () => {
		if (!generalSettings.apiKey) return;

		const btn = addCreatorBtn as HTMLButtonElement;
		btn.disabled = true;
		btn.textContent = 'Adding...';

		try {
			// Extract Twitter profile data from the content script
			const profileData = await extractProfileFromTab(tabId);

			if (!profileData) {
				btn.textContent = 'Could not extract profile';
				setTimeout(() => {
					btn.disabled = false;
					btn.textContent = 'Add as Creator';
				}, 2000);
				return;
			}

			const domainSelect = document.getElementById('creator-domain') as HTMLSelectElement;
			const domain = domainSelect?.value || 'AI/ML';

			const slug = profileData.handle.toLowerCase().replace(/[^a-z0-9-]/g, '-');

			await createCreator(generalSettings.serverUrl, generalSettings.apiKey, {
				name: profileData.name || profileData.handle,
				slug,
				description: profileData.bio || `${profileData.name || profileData.handle} — ${domain} creator`,
				bio: profileData.bio || undefined,
				expertise_domain: domain,
				avatar_url: profileData.avatarUrl || undefined,
				twitter_url: `https://x.com/${profileData.handle}`,
				author_url: profileData.websiteUrl || undefined,
				topics: [domain],
			});

			btn.textContent = 'Added!';
			// Refresh the creator dropdown
			await populateCreatorSelect();

			setTimeout(() => {
				btn.disabled = false;
				btn.textContent = 'Add as Creator';
			}, 2000);
		} catch (err: any) {
			console.error('Failed to create creator:', err);
			btn.textContent = err.message || 'Failed';
			setTimeout(() => {
				btn.disabled = false;
				btn.textContent = 'Add as Creator';
			}, 2000);
		}
	});
}

function setupSelectTweetsButton(tabId: number): void {
	const selectTweetsBtn = document.getElementById('select-tweets-btn');
	if (!selectTweetsBtn) return;

	selectTweetsBtn.addEventListener('click', async () => {
		if (!generalSettings.apiKey) return;

		const creatorId = getSelectedCreatorId();
		if (!creatorId) {
			const btn = selectTweetsBtn as HTMLButtonElement;
			btn.textContent = 'Select a creator first';
			setTimeout(() => { btn.textContent = 'Select Tweets'; }, 2000);
			return;
		}

		try {
			// Ensure content script is loaded
			await browser.runtime.sendMessage({ action: 'ensureContentScriptLoaded', tabId });

			// Send message to content script to enable selection mode
			await browser.runtime.sendMessage({
				action: 'sendMessageToTab',
				tabId,
				message: {
					action: 'enableTweetSelectionMode',
					creatorId,
					serverUrl: generalSettings.serverUrl,
					apiKey: generalSettings.apiKey,
				},
			});

			// Close the popup so the user can interact with the page
			window.close();
		} catch (err: any) {
			console.error('Failed to enable tweet selection mode:', err);
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
 * Get the currently selected creator ID from the dropdown.
 * Returns null if no creator is selected or admin section is hidden.
 */
export function getSelectedCreatorId(): string | null {
	const adminSection = document.getElementById('admin-section');
	if (!adminSection || adminSection.style.display === 'none') return null;

	const creatorSelect = document.getElementById('creator-select') as HTMLSelectElement | null;
	return creatorSelect?.value || null;
}
