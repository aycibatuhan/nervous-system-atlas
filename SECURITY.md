# Security and reporting

**Contact: batuhanayci@gmail.com.** One-person project, no bug-bounty
program; expect a reply within about a week.

This atlas is a static, client-side web application: no server, no accounts, no
logins, no cookies, no analytics, no user data. The browser loads meshes, MRI
volumes and JSON from the same origin and everything happens locally, so there
is no runtime attack surface and nothing to breach.

What is worth reporting:

- **A licence or redistribution problem** — a file in the public edition that
  should not be there. The restricted datasets (Harvard-Oxford, the Diedrichsen
  cerebellar atlas, the Brainstem Navigator, PAM50) and anything derived from
  them must never appear in a public build or on the `main` branch. **Please
  email rather than opening a public issue**, so the file can be removed before
  it is pointed at.
- **A data-integrity problem** — a mesh, MNI coordinate, label table or manifest
  entry that does not match its stated source, or an entry citing a source that
  does not support it.
- **A genuine security issue in the build tooling** — the Node scripts, the
  Python pipeline or the GitHub Actions workflows: unsafe handling of a
  downloaded file, a command-injection path, a compromised dependency.

## Not for clinical use

This is an educational reference built from group-average templates and open
literature. It is not medical advice and must never be used to diagnose or treat
a patient, or to make any decision about patient care. Clinically wrong,
misleading or dangerous content is a normal public issue, not a security report
— please open one, and say which entry and which citation.
