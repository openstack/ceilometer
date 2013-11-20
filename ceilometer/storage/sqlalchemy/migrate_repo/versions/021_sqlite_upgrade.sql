CREATE TABLE event_type (
  id INTEGER PRIMARY KEY ASC,
  desc STRING NOT NULL
);

INSERT INTO event_type
SELECT un.id, un.key
FROM unique_name un
JOIN event e ON un.id = e.unique_name_id
GROUP BY un.id;

ALTER TABLE event RENAME TO event_orig;

CREATE TABLE event (
  id INTEGER PRIMARY KEY ASC,
  generated FLOAT NOT NULL,
  message_id VARCHAR(50) UNIQUE,
  event_type_id INTEGER NOT NULL,
  FOREIGN KEY (event_type_id) REFERENCES event_type (id)
);

INSERT INTO event
SELECT id, generated, message_id, unique_name_id
FROM event_orig;

DROP TABLE event_orig;

DELETE FROM unique_name
WHERE id IN (SELECT id FROM event_type);
