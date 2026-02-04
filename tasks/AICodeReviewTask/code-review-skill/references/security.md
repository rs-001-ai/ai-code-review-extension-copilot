# Security Review Checklist

Comprehensive security review based on OWASP Top 10 and industry standards.

## Table of Contents
1. [Injection](#injection)
2. [Broken Authentication](#broken-authentication)
3. [Sensitive Data Exposure](#sensitive-data-exposure)
4. [XML External Entities (XXE)](#xxe)
5. [Broken Access Control](#broken-access-control)
6. [Security Misconfiguration](#security-misconfiguration)
7. [Cross-Site Scripting (XSS)](#xss)
8. [Insecure Deserialization](#insecure-deserialization)
9. [Using Components with Known Vulnerabilities](#vulnerable-components)
10. [Insufficient Logging & Monitoring](#logging)
11. [API Security](#api-security)
12. [Cryptography](#cryptography)

---

## Injection

### SQL Injection
```python
# BAD - SQL injection vulnerability
query = f"SELECT * FROM users WHERE id = {user_id}"

# GOOD - Parameterized query
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

### Command Injection
```python
# BAD - Command injection
os.system(f"ping {user_input}")

# GOOD - Use subprocess with list args
subprocess.run(["ping", "-c", "4", validated_host], check=True)
```

### NoSQL Injection
```javascript
// BAD - NoSQL injection in MongoDB
db.users.find({ username: req.body.username })

// GOOD - Validate and sanitize input
const username = String(req.body.username).replace(/[${}]/g, '')
db.users.find({ username: { $eq: username } })
```

### LDAP Injection
- Escape special characters: `* ( ) \ NUL`
- Use parameterized LDAP queries when available

### Check For
- [ ] String concatenation in queries (SQL, NoSQL, LDAP, GraphQL)
- [ ] User input in shell commands
- [ ] Dynamic code execution (eval, exec, Function constructor)
- [ ] Template injection in server-side rendering
- [ ] XPath/XQuery injection

---

## Broken Authentication

### Password Security
```python
# BAD - Weak hashing
password_hash = hashlib.md5(password.encode()).hexdigest()

# GOOD - Use proper password hashing
from argon2 import PasswordHasher
ph = PasswordHasher()
password_hash = ph.hash(password)
```

### Session Management
- [ ] Session IDs regenerated after login
- [ ] Secure, HttpOnly, SameSite cookie flags
- [ ] Session timeout implemented
- [ ] Logout invalidates session server-side

### Multi-Factor Authentication
- [ ] MFA available for sensitive operations
- [ ] Backup codes handled securely
- [ ] Rate limiting on MFA attempts

### Check For
- [ ] Hardcoded credentials in code
- [ ] Credentials in logs or error messages
- [ ] Weak password requirements
- [ ] Missing brute-force protection
- [ ] Predictable session tokens
- [ ] Password stored in plain text or reversible encryption

---

## Sensitive Data Exposure

### Data Classification
- PII: Names, addresses, SSN, DOB
- Financial: Credit cards, bank accounts
- Health: Medical records (HIPAA)
- Credentials: Passwords, API keys, tokens

### Encryption Requirements
```python
# BAD - Sensitive data in logs
logger.info(f"Processing payment for card {card_number}")

# GOOD - Mask sensitive data
logger.info(f"Processing payment for card ****{card_number[-4:]}")
```

### Check For
- [ ] Sensitive data encrypted at rest (AES-256)
- [ ] TLS 1.2+ for data in transit
- [ ] No sensitive data in URLs or query strings
- [ ] No sensitive data in logs
- [ ] Proper data masking in UI
- [ ] Secure deletion when required
- [ ] Environment variables for secrets (not config files)

---

## XXE

### XML External Entities
```python
# BAD - XXE vulnerable
from xml.etree.ElementTree import parse
tree = parse(user_uploaded_xml)

# GOOD - Disable external entities
import defusedxml.ElementTree as ET
tree = ET.parse(user_uploaded_xml)
```

### Check For
- [ ] XML parsers configured to disable DTDs
- [ ] External entity processing disabled
- [ ] XInclude disabled
- [ ] Consider using JSON instead of XML

---

## Broken Access Control

### Authorization Checks
```python
# BAD - Missing authorization
@app.get("/users/{user_id}/data")
def get_user_data(user_id: int):
    return db.get_user(user_id)

# GOOD - Verify authorization
@app.get("/users/{user_id}/data")
def get_user_data(user_id: int, current_user: User = Depends(get_current_user)):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(403, "Access denied")
    return db.get_user(user_id)
```

### IDOR (Insecure Direct Object Reference)
- [ ] All endpoints verify user owns/can access resource
- [ ] Use indirect references (UUIDs) instead of sequential IDs
- [ ] Server-side validation of all access requests

### Check For
- [ ] Missing authorization on endpoints
- [ ] Privilege escalation possible
- [ ] Horizontal access control (user A accessing user B's data)
- [ ] Vertical access control (user accessing admin functions)
- [ ] CORS misconfiguration allowing unauthorized origins
- [ ] JWT validation on all protected routes

---

## Security Misconfiguration

### Default Configurations
- [ ] Default credentials changed
- [ ] Debug mode disabled in production
- [ ] Directory listing disabled
- [ ] Stack traces not exposed
- [ ] Unnecessary features disabled

### Headers
```python
# Required security headers
{
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}
```

### Check For
- [ ] Security headers configured
- [ ] HTTPS enforced (HSTS)
- [ ] Error messages don't reveal system info
- [ ] Unnecessary HTTP methods disabled
- [ ] Admin interfaces properly protected

---

## XSS

### Cross-Site Scripting Prevention
```javascript
// BAD - XSS vulnerability
element.innerHTML = userInput;

// GOOD - Use textContent or sanitize
element.textContent = userInput;
// Or use DOMPurify for HTML
element.innerHTML = DOMPurify.sanitize(userInput);
```

### Context-Specific Encoding
| Context | Encoding |
|---------|----------|
| HTML body | HTML entity encode |
| HTML attribute | Attribute encode |
| JavaScript | JavaScript encode |
| URL | URL encode |
| CSS | CSS encode |

### Check For
- [ ] All user input escaped before rendering
- [ ] CSP headers configured
- [ ] DOM manipulation uses safe methods
- [ ] React/Vue/Angular auto-escaping not bypassed
- [ ] No `dangerouslySetInnerHTML` or `v-html` with user data

---

## Insecure Deserialization

### Safe Deserialization
```python
# BAD - Pickle with untrusted data
import pickle
data = pickle.loads(user_input)

# GOOD - Use safe formats
import json
data = json.loads(user_input)
```

### Check For
- [ ] No native serialization with untrusted data (pickle, serialize, Marshal)
- [ ] JSON/XML preferred for data interchange
- [ ] Schema validation on deserialized data
- [ ] Type checking after deserialization

---

## Vulnerable Components

### Dependency Security
- [ ] Dependencies regularly updated
- [ ] Security advisories monitored (Dependabot, Snyk)
- [ ] No dependencies with known CVEs
- [ ] Minimal dependency tree
- [ ] Lock files committed

### Check For
- [ ] Outdated packages with known vulnerabilities
- [ ] Unnecessary dependencies
- [ ] Dependencies from untrusted sources
- [ ] Pinned versions in production

---

## Logging

### Security Logging Requirements
```python
# Required security events to log
- Authentication attempts (success/failure)
- Authorization failures
- Input validation failures
- Security configuration changes
- Admin actions
- Data access patterns
```

### Check For
- [ ] Failed login attempts logged with IP
- [ ] Authorization failures logged
- [ ] Sensitive data NOT in logs
- [ ] Log injection prevented
- [ ] Centralized logging with alerting
- [ ] Log retention policy defined

---

## API Security

### REST API Security
- [ ] Authentication required (OAuth2, JWT, API keys)
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] Proper HTTP status codes
- [ ] Pagination on list endpoints
- [ ] No sensitive data in URLs

### GraphQL Security
- [ ] Query depth limiting
- [ ] Query complexity analysis
- [ ] Introspection disabled in production
- [ ] Field-level authorization

### Check For
- [ ] API versioning strategy
- [ ] Request size limits
- [ ] Timeout configuration
- [ ] CORS properly configured

---

## Cryptography

### Recommended Algorithms
| Purpose | Recommended | Avoid |
|---------|-------------|-------|
| Password hashing | Argon2, bcrypt, scrypt | MD5, SHA1, SHA256 alone |
| Symmetric encryption | AES-256-GCM | DES, 3DES, RC4, ECB mode |
| Asymmetric encryption | RSA-2048+, Ed25519 | RSA-1024 |
| Hashing | SHA-256, SHA-3 | MD5, SHA1 |
| TLS | 1.2, 1.3 | SSL, TLS 1.0, 1.1 |

### Check For
- [ ] No custom cryptography implementations
- [ ] Proper key management (HSM, KMS)
- [ ] Keys rotated regularly
- [ ] No hardcoded keys or IVs
- [ ] Secure random number generation
- [ ] Certificate validation enabled
