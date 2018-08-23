CREATE TABLE IF NOT EXISTS masters (user_id BIGINT, yclients_name VARCHAR, staff_id BIGINT, staff_ids_count INT DEFAULT 1);

CREATE TABLE IF NOT EXISTS reports (day VARCHAR, visit_date VARCHAR, staff_id BIGINT, photo VARCHAR, photo_id VARCHAR, record_id BIGINT, visit_id BIGINT, service_id BIGINT, goods_transactions VARCHAR, discount INT DEFAULT 0, first_cost INT, cost INT, master_comment VARCHAR, is_send BOOLEAN DEFAULT FALSE );

CREATE TABLE IF NOT EXISTS current_password (password VARCHAR);

CREATE TABLE IF NOT EXISTS authorized_users (user_id BIGINT, phone VARCHAR, logged_password VARCHAR, is_admin BOOLEAN DEFAULT FALSE);