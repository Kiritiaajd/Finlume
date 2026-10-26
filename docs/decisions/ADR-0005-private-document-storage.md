# ADR-0005: Private storage for uploaded financial documents

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

Users will upload financial documents: CSV statements in the MVP, and PDFs and annual reports later. These are among the most sensitive data Finlume holds. Django's conventional `MEDIA_ROOT` and `MEDIA_URL` pattern serves uploads publicly by URL, and is a common source of data leaks when a web server is configured to serve that directory.

## Decision

- All uploads go to **private storage**: `infrastructure.storage.private.PrivateFileSystemStorage`, configured as both the `default` and the `private_documents` storage in `STORAGES`.
  - It has no public URL. `url()` raises `PublicURLNotAllowedError`.
  - Files are written `0600` and directories `0700`.
  - The location comes from `FINLUME_PRIVATE_STORAGE_ROOT`, defaulting to `backend/var/private` (git-ignored).
- There is **no `MEDIA_URL` route** and no web-served upload directory.
- The system check **`finlume.E001`** fails if the private root is inside `STATIC_ROOT`, `STATICFILES_DIRS` or `MEDIA_ROOT`.
- Files are downloaded only through an authenticated API endpoint that checks workspace membership and streams the file. This endpoint is designed, and arrives with the documents module.
- Stored files get generated, non-guessable names. The original filename, SHA-256 hash, size, content type and uploader are kept as metadata in the database for provenance ([DATA_MODEL](../data/DATA_MODEL.md)).
- An object-storage backend (S3-compatible, private bucket, server-side encryption, short-lived signed URLs issued only after an authorisation check) can replace the filesystem class through `STORAGES` without changing callers.

## Consequences

### Positive
- A misconfigured web server cannot expose uploads, because nothing is mapped to them.
- The default storage is private too, so a `FileField` that forgets to name a storage is still safe.
- Self-hosters can keep everything on local disk.

### Negative
- Every download costs an application request; there is no CDN offload for documents.
- Backups must include the private storage volume as well as the database.
- Encryption at rest depends on the host (disk encryption) until an object store or application-level encryption is adopted.

## Alternatives considered

- **`MEDIA_ROOT` served by a reverse proxy with access rules:** fragile, because a single proxy misconfiguration exposes everything.
- **Storing files in PostgreSQL:** bloats the database and its backups, and fits poorly with large PDFs.
- **Object storage from day one:** adds a cloud dependency that conflicts with local and self-hosted operation. It stays an option behind the same interface.

## Revisit when

- PDF ingestion arrives (Phase 2): add malware scanning, size and type limits, and decide on application-level encryption.
- Hosted multi-tenant deployment is planned: adopt private object storage.
