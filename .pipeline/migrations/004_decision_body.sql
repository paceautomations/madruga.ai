-- Add body column to decisions for lossless round-trip (import → export → import).
-- Stores the original markdown body (everything after frontmatter).
ALTER TABLE decisions ADD COLUMN body TEXT;
