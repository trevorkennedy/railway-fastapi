CREATE TABLE galen_agency.uploads
(
    id UUID         NOT NULL DEFAULT gen_random_uuid(),
    token	        VARCHAR(255) NOT NULL,
    file_name	    VARCHAR(50) NOT NULL,
    content_type	VARCHAR(50),
    file_size	    INTEGER NOT NULL,
    upload_ts       timestamp NOT NULL DEFAULT NOW()
);