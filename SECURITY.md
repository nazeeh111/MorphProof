# Execution boundary

MORPHPROOF executes the supplied reference and candidate. Use trusted code only.
Separate interpreter processes, timeouts, hashed inputs and independent acceptance
logic improve repeatability; they are not an operating-system security sandbox.
A malicious module can access files, spawn processes or tamper with evidence.
Use an externally isolated container or VM for untrusted code. Do not give
credentials to test workers or coding agents.

Studio binds to loopback by default and serves only its generated evidence pages.
Reports may contain source code, paths and inputs. Review them before sharing.
Finite differential tests do not prove universal equivalence.

Report security issues through GitHub private vulnerability reporting where
available. Avoid putting secrets or exploit details in public issues.
