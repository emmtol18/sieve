import browser from './utils/browser-polyfill';
import * as highlighter from './utils/highlighter';
import { loadSettings, generalSettings } from './utils/storage-utils';
import Defuddle from 'defuddle';
import { getDomain } from './utils/string-utils';
import { createMarkdownContent } from './utils/markdown-converter';
import { extractTwitterProfile, extractTweetContent } from './utils/twitter-extractor';
import { batchCapture } from './utils/sieve-api-client';

declare global {
	interface Window {
		obsidianHighlighterInitialized?: boolean;
	}
}

// Use a self-executing function to create a closure
// This allows the script to be re-executed without redeclaring variables
(function() {
	// Check if the script has already been initialized
	if (window.hasOwnProperty('obsidianHighlighterInitialized')) {
		return;  // Exit if already initialized
	}

	// Mark as initialized
	window.obsidianHighlighterInitialized = true;

	let isHighlighterMode = false;
	const iframeId = 'obsidian-clipper-iframe';
	const containerId = 'obsidian-clipper-container';

	function removeContainer(container: HTMLElement) {
		container.classList.add('is-closing');
		container.addEventListener('animationend', () => {
			container.remove();
		}, { once: true });
	}

	async function toggleIframe() {
		const existingContainer = document.getElementById(containerId);
		if (existingContainer) {
			removeContainer(existingContainer);
			return;
		}

		const container = document.createElement('div');
		container.id = containerId;
		container.classList.add('is-open');

		const { clipperIframeWidth, clipperIframeHeight } = await browser.storage.local.get(['clipperIframeWidth', 'clipperIframeHeight']);
		if (clipperIframeWidth) {
			container.style.width = `${clipperIframeWidth}px`;
		}
		if (clipperIframeHeight) {
			container.style.height = `${clipperIframeHeight}px`;
		}

		const iframe = document.createElement('iframe');
		iframe.id = iframeId;
		iframe.src = browser.runtime.getURL('side-panel.html?context=iframe');
		container.appendChild(iframe);

		// Add resize handle (left side only)
		const handle = document.createElement('div');
		handle.className = `obsidian-clipper-resize-handle obsidian-clipper-resize-handle-w`;
		container.appendChild(handle);
		addResizeListener(container, handle, 'w');

		const southHandle = document.createElement('div');
		southHandle.className = `obsidian-clipper-resize-handle obsidian-clipper-resize-handle-s`;
		container.appendChild(southHandle);
		addResizeListener(container, southHandle, 's');

		const southWestHandle = document.createElement('div');
		southWestHandle.className = 'obsidian-clipper-resize-handle obsidian-clipper-resize-handle-sw';
		container.appendChild(southWestHandle);
		addResizeListener(container, southWestHandle, 'sw');

		document.body.appendChild(container);
	}

	function addResizeListener(container: HTMLElement, handle: HTMLElement, direction: string) {
		let isResizing = false;
		let startX: number, startY: number, startWidth: number, startHeight: number, startLeft: number, startTop: number;
	
		handle.onmousedown = (e) => {
			e.stopPropagation();
			isResizing = true;
			startX = e.clientX;
			startY = e.clientY;
			startWidth = container.offsetWidth;
			startHeight = container.offsetHeight;
			startLeft = container.offsetLeft;
			startTop = container.offsetTop;

			document.body.style.cursor = window.getComputedStyle(handle).cursor;
	
			const iframe = container.querySelector('#obsidian-clipper-iframe');
			if (iframe) iframe.classList.add('is-resizing');
	
			document.onmousemove = (moveEvent) => {
				if (!isResizing) return;
	
				const dx = moveEvent.clientX - startX;
				const dy = moveEvent.clientY - startY;

				const minWidth = parseInt(container.style.minWidth) || 200;
				const minHeight = parseInt(container.style.minHeight) || 200;
	
				if (direction.includes('e')) {
					let newWidth = startWidth + dx;
					if (newWidth < minWidth) newWidth = minWidth;
					container.style.width = `${newWidth}px`;
				}
				if (direction.includes('w')) {
					let newWidth = startWidth - dx;
					if (newWidth < minWidth) {
						newWidth = minWidth;
					}
					container.style.width = `${newWidth}px`;
				}
				if (direction.includes('s')) {
					let newHeight = startHeight + dy;
					if (newHeight < minHeight) newHeight = minHeight;
					container.style.height = `${newHeight}px`;
				}
				if (direction.includes('n')) {
					let newHeight = startHeight - dy;
					let newTop = startTop + dy;
					if (newHeight < minHeight) {
						newHeight = minHeight;
						newTop = startTop + startHeight - minHeight;
					}
					container.style.height = `${newHeight}px`;
					container.style.top = `${newTop}px`;
				}
			};
	
			document.onmouseup = () => {
				isResizing = false;
				const iframe = container.querySelector('#obsidian-clipper-iframe');
				if (iframe) iframe.classList.remove('is-resizing');
				document.body.style.cursor = '';
				
				const newWidth = container.offsetWidth;
				const newHeight = container.offsetHeight;
				browser.storage.local.set({ clipperIframeWidth: newWidth, clipperIframeHeight: newHeight });

				document.onmousemove = null;
				document.onmouseup = null;
			};
		};
	}

	// Firefox
	browser.runtime.sendMessage({ action: "contentScriptLoaded" });

	interface ContentResponse {
		content: string;
		selectedHtml: string;
		extractedContent: { [key: string]: string };
		schemaOrgData: any;
		fullHtml: string;
		highlights: string[];
		title: string;
		description: string;
		domain: string;
		favicon: string;
		image: string;
		parseTime: number;
		published: string;
		author: string;
		site: string;
		wordCount: number;
		metaTags: { name?: string | null; property?: string | null; content: string | null }[];
	}

	browser.runtime.onMessage.addListener((request: any, sender, sendResponse) => {
		if (request.action === "ping") {
			sendResponse({});
			return true;
		}

		if (request.action === "toggle-iframe") {
			toggleIframe().then(() => {
				sendResponse({ success: true });
			});
			return true;
		}

		if (request.action === "close-iframe") {
			const existingContainer = document.getElementById(containerId);
			if (existingContainer) {
				removeContainer(existingContainer);
			}
			return;
		}

		if (request.action === "copy-text-to-clipboard") {
			const textArea = document.createElement("textarea");
			textArea.value = request.text;
			document.body.appendChild(textArea);
			textArea.select();
			try {
				document.execCommand('copy');
				sendResponse({success: true});
			} catch (err) {
				sendResponse({success: false});
			}
			document.body.removeChild(textArea);
			return true;
		}

		if (request.action === "copyMarkdownToClipboard") {
			try {
				// Extract page content using Defuddle
				const defuddled = new Defuddle(document, { url: document.URL }).parse();

				// Convert HTML content to markdown
				const markdown = createMarkdownContent(defuddled.content, document.URL);

				// Copy to clipboard
				const textArea = document.createElement("textarea");
				textArea.value = markdown;
				document.body.appendChild(textArea);
				textArea.select();
				document.execCommand('copy');
				document.body.removeChild(textArea);

				sendResponse({ success: true });
			} catch (err) {
				console.error('Failed to copy markdown to clipboard:', err);
				sendResponse({ success: false, error: (err as Error).message });
			}
			return true;
		}

		if (request.action === "getPageContent") {
			let selectedHtml = '';
			const selection = window.getSelection();
			
			if (selection && selection.rangeCount > 0) {
				const range = selection.getRangeAt(0);
				const clonedSelection = range.cloneContents();
				const div = document.createElement('div');
				div.appendChild(clonedSelection);
				selectedHtml = div.innerHTML;
			}

			const extractedContent: { [key: string]: string } = {};

			// Process with Defuddle first while we have access to the document
			const defuddled = new Defuddle(document, { url: document.URL }).parse();

			// Create a new DOMParser
			const parser = new DOMParser();
			// Parse the document's HTML
			const doc = parser.parseFromString(document.documentElement.outerHTML, 'text/html');

			// Remove all script and style elements
			doc.querySelectorAll('script, style').forEach(el => el.remove());

			// Remove style attributes from all elements
			doc.querySelectorAll('*').forEach(el => el.removeAttribute('style'));

			// Convert all relative URLs to absolute
			doc.querySelectorAll('[src], [href]').forEach(element => {
				['src', 'href', 'srcset'].forEach(attr => {
					const value = element.getAttribute(attr);
					if (!value) return;
					
					if (attr === 'srcset') {
						const newSrcset = value.split(',').map(src => {
							const [url, size] = src.trim().split(' ');
							try {
								const absoluteUrl = new URL(url, document.baseURI).href;
								return `${absoluteUrl}${size ? ' ' + size : ''}`;
							} catch (e) {
								return src;
							}
						}).join(', ');
						element.setAttribute(attr, newSrcset);
					} else if (!value.startsWith('http') && !value.startsWith('data:') && !value.startsWith('#') && !value.startsWith('//')) {
						try {
							const absoluteUrl = new URL(value, document.baseURI).href;
							element.setAttribute(attr, absoluteUrl);
						} catch (e) {
							console.warn(`Failed to process ${attr} URL:`, value);
						}
					}
				});
			});

			// Get the modified HTML without scripts, styles, and style attributes
			const cleanedHtml = doc.documentElement.outerHTML;

			const response: ContentResponse = {
				author: defuddled.author,
				content: defuddled.content,
				description: defuddled.description,
				domain: getDomain(document.URL),
				extractedContent: extractedContent,
				favicon: defuddled.favicon,
				fullHtml: cleanedHtml,
				highlights: highlighter.getHighlights(),
				image: defuddled.image,
				parseTime: defuddled.parseTime,
				published: defuddled.published,
				schemaOrgData: defuddled.schemaOrgData,
				selectedHtml: selectedHtml,
				site: defuddled.site,
				title: defuddled.title,
				wordCount: defuddled.wordCount,
				metaTags: defuddled.metaTags || []
			};
			sendResponse(response);
		} else if (request.action === "extractContent") {
			const content = extractContentBySelector(request.selector, request.attribute, request.extractHtml);
			sendResponse({ content: content });
		} else if (request.action === "paintHighlights") {
			highlighter.loadHighlights().then(() => {
				if (generalSettings.alwaysShowHighlights) {
					highlighter.applyHighlights();
				}
				sendResponse({ success: true });
			});
			return true;
		} else if (request.action === "setHighlighterMode") {
			isHighlighterMode = request.isActive;
			highlighter.toggleHighlighterMenu(isHighlighterMode);
			updateHasHighlights();
			sendResponse({ success: true });
			return true;
		} else if (request.action === "getHighlighterMode") {
			browser.runtime.sendMessage({ action: "getHighlighterMode" }).then(sendResponse);
			return true;
		} else if (request.action === "toggleHighlighter") {
			highlighter.toggleHighlighterMenu(request.isActive);
			updateHasHighlights();
			sendResponse({ success: true });
		} else if (request.action === "highlightSelection") {
			highlighter.toggleHighlighterMenu(request.isActive);
			const selection = window.getSelection();
			if (selection && !selection.isCollapsed) {
				highlighter.handleTextSelection(selection);
			}
			updateHasHighlights();
			sendResponse({ success: true });
		} else if (request.action === "highlightElement") {
			highlighter.toggleHighlighterMenu(request.isActive);
			if (request.targetElementInfo) {
				const { mediaType, srcUrl, pageUrl } = request.targetElementInfo;
				
				let elementToHighlight: Element | null = null;

				// Function to compare URLs, handling both absolute and relative paths
				const urlMatches = (elementSrc: string, targetSrc: string) => {
					const elementUrl = new URL(elementSrc, pageUrl);
					const targetUrl = new URL(targetSrc, pageUrl);
					return elementUrl.href === targetUrl.href;
				};

				// Try to find the element using the src attribute
				elementToHighlight = document.querySelector(`${mediaType}[src="${srcUrl}"]`);

				// If not found, try with relative URL
				if (!elementToHighlight) {
					const relativeSrc = new URL(srcUrl).pathname;
					elementToHighlight = document.querySelector(`${mediaType}[src="${relativeSrc}"]`);
				}

				// If still not found, iterate through all elements of the media type
				if (!elementToHighlight) {
					const elements = Array.from(document.getElementsByTagName(mediaType));
					for (const el of elements) {
						if (el instanceof HTMLImageElement || el instanceof HTMLVideoElement || el instanceof HTMLAudioElement) {
							if (urlMatches(el.src, srcUrl)) {
								elementToHighlight = el;
								break;
							}
						}
					}
				}

				if (elementToHighlight) {
					const xpath = highlighter.getElementXPath(elementToHighlight);
					highlighter.highlightElement(elementToHighlight);
				} else {
					console.warn('Could not find element to highlight. Info:', request.targetElementInfo);
				}
			}
			updateHasHighlights();
			sendResponse({ success: true });
		} else if (request.action === "clearHighlights") {
			highlighter.clearHighlights();
			updateHasHighlights();
			sendResponse({ success: true });
		} else if (request.action === "getHighlighterState") {
			browser.runtime.sendMessage({ action: "getHighlighterMode" })
				.then(response => {
					sendResponse(response);
				})
				.catch(error => {
					console.error("Error getting highlighter mode:", error);
					sendResponse({ isActive: false });
				});
			return true;
		} else if (request.action === "toggleReaderMode") {
			// Forward the request to the background script to inject reader mode if needed
			browser.runtime.sendMessage({ action: "toggleReaderMode", tabId: sender.tab?.id })
				.then(sendResponse)
				.catch(error => {
					console.error("Error toggling reader mode:", error);
					sendResponse({ success: false, error: error instanceof Error ? error.message : 'Unknown error' });
				});
			return true;
		} else if (request.action === "showSieveToast") {
			showSieveToast(request.title, request.capsuleId, request.serverUrl);
			sendResponse({ success: true });
		} else if (request.action === "showSieveErrorToast") {
			showSieveErrorToast(request.message);
			sendResponse({ success: true });
		} else if (request.action === "extractTwitterProfile") {
			const profile = extractTwitterProfile();
			sendResponse(profile);
		} else if (request.action === "enableTweetSelectionMode") {
			enableTweetSelectionMode(request.creatorId, request.serverUrl, request.apiKey);
			sendResponse({ success: true });
		}
		return true;
	});

	function showSieveToast(title: string, capsuleId: string, serverUrl: string): void {
		const existing = document.getElementById('sieve-toast');
		if (existing) existing.remove();

		const toast = document.createElement('div');
		toast.id = 'sieve-toast';
		toast.style.cssText = `
			position: fixed; bottom: 24px; right: 24px; z-index: 2147483647;
			background: #1a1a2e; color: #e0e0e0; border: 1px solid #333;
			border-radius: 12px; padding: 16px 20px; max-width: 360px;
			box-shadow: 0 8px 32px rgba(0,0,0,0.4);
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
			font-size: 14px; line-height: 1.4; cursor: pointer;
			transition: opacity 0.3s, transform 0.3s;
			opacity: 0; transform: translateY(10px);
		`;

		const headerEl = document.createElement('div');
		headerEl.style.cssText = 'font-weight: 600; margin-bottom: 4px; color: #7c6bf5;';
		headerEl.textContent = 'Saved to your Sieve';

		const titleEl = document.createElement('div');
		titleEl.style.cssText = 'color: #ccc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';
		titleEl.textContent = title;

		toast.appendChild(headerEl);
		toast.appendChild(titleEl);

		toast.addEventListener('click', () => {
			window.open(`${serverUrl}/capsule/${encodeURIComponent(capsuleId)}`, '_blank');
			toast.remove();
		});

		document.body.appendChild(toast);
		requestAnimationFrame(() => {
			toast.style.opacity = '1';
			toast.style.transform = 'translateY(0)';
		});
		setTimeout(() => {
			toast.style.opacity = '0';
			toast.style.transform = 'translateY(10px)';
			setTimeout(() => toast.remove(), 300);
		}, 4000);
	}

	function showSieveErrorToast(message: string): void {
		const existing = document.getElementById('sieve-toast');
		if (existing) existing.remove();

		const toast = document.createElement('div');
		toast.id = 'sieve-toast';
		toast.style.cssText = `
			position: fixed; bottom: 24px; right: 24px; z-index: 2147483647;
			background: #2e1a1a; color: #e0e0e0; border: 1px solid #4a2020;
			border-radius: 12px; padding: 16px 20px; max-width: 360px;
			box-shadow: 0 8px 32px rgba(0,0,0,0.4);
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
			font-size: 14px; line-height: 1.4;
			transition: opacity 0.3s, transform 0.3s;
			opacity: 0; transform: translateY(10px);
		`;

		const headerEl = document.createElement('div');
		headerEl.style.cssText = 'font-weight: 600; margin-bottom: 4px; color: #f55;';
		headerEl.textContent = 'Capture failed';

		const messageEl = document.createElement('div');
		messageEl.style.cssText = 'color: #ccc;';
		messageEl.textContent = message;

		toast.appendChild(headerEl);
		toast.appendChild(messageEl);

		document.body.appendChild(toast);
		requestAnimationFrame(() => {
			toast.style.opacity = '1';
			toast.style.transform = 'translateY(0)';
		});
		setTimeout(() => {
			toast.style.opacity = '0';
			toast.style.transform = 'translateY(10px)';
			setTimeout(() => toast.remove(), 300);
		}, 5000);
	}

	function extractContentBySelector(selector: string, attribute?: string, extractHtml: boolean = false): string | string[] {
		try {
			const elements = document.querySelectorAll(selector);
			
			if (elements.length > 1) {
				return Array.from(elements).map(el => {
					if (attribute) {
						return el.getAttribute(attribute) || '';
					}
					return extractHtml ? el.outerHTML : el.textContent?.trim() || '';
				});
			} else if (elements.length === 1) {
				if (attribute) {
					return elements[0].getAttribute(attribute) || '';
				}
				return extractHtml ? elements[0].outerHTML : elements[0].textContent?.trim() || '';
			} else {
				console.log(`No elements found for selector: ${selector}`);
				return '';
			}
		} catch (error) {
			console.error('Error in extractContentBySelector:', error, { selector, attribute, extractHtml });
			return '';
		}
	}

	function updateHasHighlights() {
		const hasHighlights = highlighter.getHighlights().length > 0;
		browser.runtime.sendMessage({ action: "updateHasHighlights", hasHighlights });
	}

	async function initializeHighlighter() {
		await loadSettings();
		await highlighter.loadHighlights();
		
		if (generalSettings.alwaysShowHighlights) {
			highlighter.applyHighlights();
		}
		
		updateHasHighlights();
	}

	// Initialize highlighter
	initializeHighlighter();

	// Call updateHasHighlights when the page loads
	window.addEventListener('load', updateHasHighlights);

	// Deactivate highlighter mode on unload
	function handlePageUnload() {
		if (isHighlighterMode) {
			highlighter.toggleHighlighterMenu(false);
			browser.runtime.sendMessage({ action: "highlighterModeChanged", isActive: false });
			browser.storage.local.set({ isHighlighterMode: false });
		}
	}

	window.addEventListener('beforeunload', handlePageUnload);

	// Listen for custom events from the reader script
	document.addEventListener('obsidian-reader-init', async () => {
		// Find the highlighter button
		const button = document.querySelector('[data-action="toggle-highlighter"]');
		if (button) {
			// Handle highlighter button clicks
			button.addEventListener('click', async (e) => {
				try {
					// First try to get the tab ID from the background script
					const response = await browser.runtime.sendMessage({ action: "ensureContentScriptLoaded" });
					
					let tabId: number | undefined;
					if (response && typeof response === 'object') {
						tabId = (response as { tabId: number }).tabId;
					}

					// If we didn't get a tab ID, try to get it from the background script
					if (!tabId) {
						try {
							const response = await browser.runtime.sendMessage({ action: "getActiveTab" }) as { tabId?: number; error?: string };
							if (response && !response.error && response.tabId) {
								tabId = response.tabId;
							}
						} catch (error) {
							console.error('[Content] Failed to get tab ID from background script:', error);
						}
					}

					if (tabId) {
						await browser.runtime.sendMessage({ action: "toggleHighlighterMode", tabId });
					} else {
						console.error('[Content]','Could not determine tab ID');
					}
				} catch (error) {
					console.error('[Content]','Error in toggle flow:', error);
				}
			});
		}
	});

	let selectionModeActive = false;
	const selectedTweets = new Set<Element>();

	function enableTweetSelectionMode(creatorId: string, serverUrl: string, apiKey: string): void {
		if (selectionModeActive) return;
		selectionModeActive = true;
		selectedTweets.clear();

		// Inject selection styles
		const style = document.createElement('style');
		style.id = 'sieve-selection-style';
		style.textContent = `
			[data-testid="tweet"] {
				cursor: pointer !important;
				transition: border-left 0.15s, background 0.15s !important;
			}
			[data-testid="tweet"]:hover {
				border-left: 3px solid #7c6bf5 !important;
			}
			[data-testid="tweet"].sieve-selected {
				border-left: 3px solid #7c6bf5 !important;
				background: rgba(124, 107, 245, 0.08) !important;
			}
		`;
		document.head.appendChild(style);

		// Add click handlers to tweets
		document.addEventListener('click', tweetClickHandler, true);

		// Create floating action bar
		createSelectionBar(creatorId, serverUrl, apiKey);
	}

	function tweetClickHandler(e: MouseEvent): void {
		if (!selectionModeActive) return;

		const target = e.target as Element;
		if (target.closest('a[href]') || target.closest('button') || target.closest('[role="button"]')) {
			return;
		}

		const tweetEl = target.closest('[data-testid="tweet"]');
		if (!tweetEl) return;

		e.preventDefault();
		e.stopPropagation();

		if (selectedTweets.has(tweetEl)) {
			selectedTweets.delete(tweetEl);
			tweetEl.classList.remove('sieve-selected');
		} else {
			selectedTweets.add(tweetEl);
			tweetEl.classList.add('sieve-selected');
		}

		updateSelectionCount();
	}

	function createSelectionBar(creatorId: string, serverUrl: string, apiKey: string): void {
		const bar = document.createElement('div');
		bar.id = 'sieve-selection-bar';
		bar.style.cssText = `
			position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
			z-index: 2147483647; background: #1a1a2e; color: #e0e0e0;
			border: 1px solid #333; border-radius: 12px; padding: 12px 20px;
			display: flex; align-items: center; gap: 16px;
			box-shadow: 0 8px 32px rgba(0,0,0,0.4);
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
			font-size: 14px;
		`;

		const countEl = document.createElement('span');
		countEl.id = 'sieve-selection-count';
		countEl.textContent = '0 selected';

		const captureBtn = document.createElement('button');
		captureBtn.textContent = 'Capture All';
		captureBtn.style.cssText = `
			background: #7c6bf5; color: white; border: none; border-radius: 6px;
			padding: 8px 16px; cursor: pointer; font-size: 14px; font-weight: 600;
		`;
		captureBtn.addEventListener('click', () => handleBatchCapture(creatorId, serverUrl, apiKey));

		const cancelBtn = document.createElement('button');
		cancelBtn.textContent = 'Cancel';
		cancelBtn.style.cssText = `
			background: transparent; color: #999; border: 1px solid #444;
			border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 14px;
		`;
		cancelBtn.addEventListener('click', disableSelectionMode);

		bar.appendChild(countEl);
		bar.appendChild(captureBtn);
		bar.appendChild(cancelBtn);
		document.body.appendChild(bar);
	}

	function updateSelectionCount(): void {
		const countEl = document.getElementById('sieve-selection-count');
		if (countEl) {
			countEl.textContent = `${selectedTweets.size} selected`;
		}
	}

	async function handleBatchCapture(creatorId: string, serverUrl: string, apiKey: string): Promise<void> {
		if (selectedTweets.size === 0) return;

		const items: { content: string; source_url?: string }[] = [];
		for (const tweetEl of selectedTweets) {
			const extracted = extractTweetContent(tweetEl);
			if (extracted) {
				items.push({
					content: extracted.text,
					source_url: extracted.url || undefined,
				});
			}
		}

		if (items.length === 0) {
			showSieveErrorToast('No tweet text could be extracted from selection');
			disableSelectionMode();
			return;
		}

		// Update UI to show progress
		const captureBtn = document.querySelector('#sieve-selection-bar button') as HTMLButtonElement;
		if (captureBtn) {
			captureBtn.disabled = true;
			captureBtn.textContent = `Capturing ${items.length}...`;
		}

		try {
			const result = await batchCapture(serverUrl, apiKey, {
				items,
				creator_id: creatorId,
			});

			const message = `${result.succeeded}/${result.total} capsules created` +
				(result.failed > 0 ? ` (${result.failed} failed)` : '');

			showSieveToast(message, '', serverUrl);
		} catch (err: any) {
			showSieveErrorToast(err.message || 'Batch capture failed');
		}

		disableSelectionMode();
	}

	function disableSelectionMode(): void {
		selectionModeActive = false;
		document.removeEventListener('click', tweetClickHandler, true);

		// Remove selection styling
		for (const el of selectedTweets) {
			el.classList.remove('sieve-selected');
		}
		selectedTweets.clear();

		// Remove injected elements
		document.getElementById('sieve-selection-style')?.remove();
		document.getElementById('sieve-selection-bar')?.remove();
	}

})();
