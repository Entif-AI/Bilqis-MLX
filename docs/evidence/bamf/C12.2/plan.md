# C12.2 / #526 local directory exchange

Consumed Lane C/unified `70e37ae27214061dcc1712503eae6741a2e3781e`.
The issue branch consumes the same-Lane-C #525/#668 source `30385b0f` through a
normal merge. This does not merge that draft into unified or claim acceptance.

Implement the prescribed first local two-node exchange using the existing
CognitivePackage canonical wire format and stage_import compatibility owner.
No server, networking framework, second manifest schema or execution loader.

`publish_package(package, directory) -> Path`: validate source clearance and
canonical package identity before making a directory; publish `<digest>.json`
with a flushed/fsynced temporary file, create-only atomic link and directory
fsync. Existing identical bytes converge; conflicting files and symlinks reject.
Never overwrite an existing entry. Always clean temporary files.

`receive_package(sender, receiver, digest, binding, *, max_wire_bytes) ->
StagedExchange`: bounded read of a regular non-symlink package file, verify raw
SHA-256 and existing canonical decoder/clearance contracts, then call the existing
stage_import. Only after all gates pass publish identical canonical bytes under
the receiver staging directory. StagedExchange is frozen and contains the package,
plan and receiver path. It does not activate, execute or apply a tensor delta.
The sender directory is a trusted local path; arbitrary remote path traversal or
untrusted parent-directory ownership is not introduced as an authority.

Tests first fail for the missing API. Exercise two actual temporary node
directories: exact transfer, independent cold decode, byte/mtime preservation,
idempotency, heterogeneous teaching-only transfer, incompatible delta refusal
before receiver mutation, tampering/noncanonical encoding, symlink refusal,
bounded wire reads and interrupted publication cleanup. Public-clearance checks
remain the existing owner. Payload bytes never execute.

This implements #526's local exchange/staging clause, not full #526 acceptance.
Native compatible delta application, whole-capability retention before activation,
optimizer slice reset, rollback, next-update and cold-resume proofs still require
accepted B13/C05 and downstream #527. Independent EGM is pending while reviewer
workspace credits are unavailable. Keep the PR draft and #526 open.
