USE smart_waste_db;

CREATE TABLE IF NOT EXISTS users (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(100)    NOT NULL UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    role            VARCHAR(20)     NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_role_valid CHECK (role IN ('CITIZEN', 'STAFF', 'ADMIN'))
);

-- Add reported_by_user_id to waste_reports
ALTER TABLE waste_reports
ADD COLUMN reported_by_user_id INT NULL,
ADD CONSTRAINT fk_waste_reports_user
    FOREIGN KEY (reported_by_user_id) REFERENCES users(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
