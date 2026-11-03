-- Urban Pulse NYC: database and table schema
-- Run order: this file is executed by src/load_mysql.py, or paste into MySQL Workbench.
CREATE DATABASE IF NOT EXISTS urban_pulse_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE urban_pulse_db;

-- Staging table: data lands here first, gets checked, then is published
DROP TABLE IF EXISTS service_requests_staging;
CREATE TABLE service_requests_staging (
    unique_key                     BIGINT        NOT NULL PRIMARY KEY,
    created_date                   DATETIME      NOT NULL,
    closed_date                    DATETIME      NULL,
    due_date                       DATETIME      NULL,
    resolution_action_updated_date DATETIME      NULL,
    agency                         VARCHAR(20)   NULL,
    agency_name                    VARCHAR(255)  NULL,
    complaint_type                 VARCHAR(120)  NULL,
    descriptor                     VARCHAR(255)  NULL,
    location_type                  VARCHAR(120)  NULL,
    status                         VARCHAR(40)   NULL,
    resolution_description         TEXT          NULL,
    borough                        VARCHAR(30)   NULL,
    incident_zip                   VARCHAR(12)   NULL,
    city                           VARCHAR(120)  NULL,
    incident_address               VARCHAR(255)  NULL,
    street_name                    VARCHAR(255)  NULL,
    address_type                   VARCHAR(40)   NULL,
    community_board                VARCHAR(60)   NULL,
    council_district               VARCHAR(10)   NULL,
    police_precinct                VARCHAR(60)   NULL,
    open_data_channel_type         VARCHAR(30)   NULL,
    park_borough                   VARCHAR(30)   NULL,
    latitude                       DECIMAL(10,7) NULL,
    longitude                      DECIMAL(10,7) NULL,
    -- quality flags (1 = look at this row)
    flag_closed_before_created     TINYINT NOT NULL DEFAULT 0,
    flag_zero_duration             TINYINT NOT NULL DEFAULT 0,
    flag_future_date               TINYINT NOT NULL DEFAULT 0,
    flag_status_closed_no_date     TINYINT NOT NULL DEFAULT 0,
    flag_date_but_not_closed       TINYINT NOT NULL DEFAULT 0,
    flag_midnight_created          TINYINT NOT NULL DEFAULT 0,
    flag_missing_coords            TINYINT NOT NULL DEFAULT 0,
    flag_coords_outside_nyc        TINYINT NOT NULL DEFAULT 0,
    flag_unspecified_borough       TINYINT NOT NULL DEFAULT 0,
    -- derived fields
    is_closed                      TINYINT NOT NULL,
    resolution_hours               DECIMAL(12,3) NULL,
    created_year                   SMALLINT NOT NULL,
    created_month                  CHAR(7)  NOT NULL,
    created_weekday                VARCHAR(10) NOT NULL,
    created_weekday_num            TINYINT  NOT NULL,
    created_hour                   TINYINT  NOT NULL,
    res_outlier_iqr                TINYINT  NULL,
    over_72h                       TINYINT  NULL,
    INDEX idx_created (created_date),
    INDEX idx_complaint (complaint_type),
    INDEX idx_agency (agency),
    INDEX idx_borough (borough),
    INDEX idx_month (created_month)
) ENGINE=InnoDB;
