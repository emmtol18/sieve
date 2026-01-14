# Project Guidance

## Workflow Instructions

### After Completing a Feature or Change

Always conclude work on a feature, bug fix, or any code change with:

1. **Git commit message suggestion** - Provide a clear, conventional commit message following this format:
   ```
   <type>: <short description>

   <optional body explaining what and why>
   ```
   Types: `feat`, `fix`, `refactor`, `docs`, `style`, `test`, `chore`

2. **Summary of changes** - List what files were modified/created and what changed:
   - Files added
   - Files modified
   - Key changes made
   - Any breaking changes or important notes

### Example

```
Suggested commit:
feat: add user authentication with JWT tokens

Changes made:
- Created: src/auth/jwt.ts (JWT token generation/validation)
- Modified: src/routes/api.ts (added auth middleware)
- Modified: src/types/user.ts (added token fields)
```
