CREATE TABLE galen_agency.uploads
(
    id    	        serial primary key,
    token	        VARCHAR(255) not null,
    file_name	    VARCHAR(50),
    content_type	VARCHAR(50),
    file_size	    INTEGER NOT NULL,
    upload_ts       timestamp NOT NULL DEFAULT NOW()
);