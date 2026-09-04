# Ideas

## Compress the prompt payload

Explore applying gzip compression to the textual prompt stored as the compressed image payload.
Because the payload is text, this may reduce artifact size and improve the measured compression
ratio.

Do not implement this yet. Before changing the format, measure the size reduction across the
checked-in artifacts, include all container overhead in every ratio, and determine the required
format-version and compatibility changes.
