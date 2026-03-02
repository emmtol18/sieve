// Prompt variables were handled by the interpreter feature which has been removed.
// The server-side LLM now handles all extraction.
export async function processPrompt(match: string, variables: { [key: string]: string }, currentUrl: string): Promise<string> {
	return '';
}
