ALTER TABLE event RENAME TO event_orig;

INSERT INTO unique_name
SELECT et.id, et.desc
FROM event_type et;

CREATE TABLE event (
  id INTEGER PRIMARY KEY ASC,
  generated FLOAT NOT NULL,
  message_id VARCHAR(50) UNIQUE,
  unique_name_id INTEGER NOT NULL,
  FOREIGN KEY (unique_name_id) REFERENCES unique_name (id)
);

INSERT INTO event
SELECT id, generated, message_id, event_type_id
FROM event_orig;

DROP TABLE event_orig;
DROP TABLE event_type;
