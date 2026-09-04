-- 只读账号（RAG 服务用）
CREATE USER IF NOT EXISTS 'rag_ro'@'%' IDENTIFIED BY 'ro123';
CREATE USER IF NOT EXISTS 'rag_ro'@'localhost' IDENTIFIED BY 'ro123';
GRANT SELECT ON yoyac_pv.* TO 'rag_ro'@'%';
GRANT SELECT ON yoyac_pv.* TO 'rag_ro'@'localhost';
FLUSH PRIVILEGES;

-- 光伏业务示例表

-- 1. 产品表（静态主数据）
CREATE TABLE IF NOT EXISTS products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  model VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(128) NOT NULL,
  rated_power_watt INT NOT NULL COMMENT '额定功率(W)',
  cell_type VARCHAR(32) COMMENT '电池片类型: 单晶/多晶',
  efficiency_pct DECIMAL(4,2) COMMENT '组件效率(%)',
  warranty_years INT COMMENT '质保年限',
  price_cny DECIMAL(10,2) COMMENT '出厂价(元)',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_model (model),
  INDEX idx_power (rated_power_watt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 客户表（含敏感字段）
CREATE TABLE IF NOT EXISTS customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  phone VARCHAR(20),
  id_card VARCHAR(18) COMMENT '身份证号(敏感)',
  address VARCHAR(255),
  company VARCHAR(128),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 订单表
CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_no VARCHAR(32) NOT NULL UNIQUE,
  customer_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  unit_price DECIMAL(10,2),
  total_price DECIMAL(12,2),
  order_date DATE NOT NULL,
  status ENUM('pending','paid','shipped','installed','closed') DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_customer (customer_id),
  INDEX idx_product (product_id),
  INDEX idx_date (order_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 设备安装表
CREATE TABLE IF NOT EXISTS installations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  device_no VARCHAR(32) NOT NULL UNIQUE,
  order_id INT NOT NULL,
  customer_id INT NOT NULL,
  site_name VARCHAR(128),
  install_date DATE NOT NULL,
  warranty_until DATE COMMENT '质保到期日',
  location VARCHAR(255),
  power_actual_watt INT,
  status ENUM('active','maintained','replaced','scraped') DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_customer (customer_id),
  INDEX idx_warranty (warranty_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 售后工单表
CREATE TABLE IF NOT EXISTS service_tickets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  ticket_no VARCHAR(32) NOT NULL UNIQUE,
  installation_id INT NOT NULL,
  customer_id INT NOT NULL,
  issue_type ENUM('warranty','repair','inspection','consultation') DEFAULT 'repair',
  description TEXT,
  priority ENUM('low','medium','high','urgent') DEFAULT 'medium',
  status ENUM('open','in_progress','resolved','closed') DEFAULT 'open',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP NULL,
  INDEX idx_installation (installation_id),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 灌示例数据

INSERT INTO products (model, name, rated_power_watt, cell_type, efficiency_pct, warranty_years, price_cny) VALUES
('FH-M10-550',  'FH-M10 单晶550W',       550, '单晶', 20.80, 25, 298.00),
('FH-M10-560',  'FH-M10 单晶560W',       560, '单晶', 20.95, 25, 305.00),
('FH-M10-575',  'FH-M10 单晶575W',       575, '单晶', 21.10, 25, 318.00),
('FH-POLY-300', 'FH-POLY 多晶300W',      300, '多晶', 17.80, 20, 180.00),
('FH-M10-700',  'FH-M10 单晶700W(大型)', 700, '单晶', 21.50, 25, 395.00);

INSERT INTO customers (name, phone, id_card, address, company) VALUES
('张三',   '13800138001', '410102198501011234', '河南省濮阳市华龙区XX路',   '濮阳新能源有限公司'),
('李四',   '13800138002', '110101199001015678', '北京市朝阳区XX小区',        '北京阳光电力有限公司'),
('王五',   '13800138003', '440101198805019012', '广州市天河区XX大道',        '广州绿能科技有限公司');

INSERT INTO orders (order_no, customer_id, product_id, quantity, unit_price, total_price, order_date, status) VALUES
('ORD2024001', 1, 1, 50,  298.00, 14900.00, '2024-03-15', 'installed'),
('ORD2024002', 1, 3, 30,  318.00,  9540.00, '2024-06-20', 'shipped'),
('ORD2024003', 2, 4, 20,  395.00,  7900.00, '2024-08-10', 'paid'),
('ORD2024004', 3, 1, 100, 298.00, 29800.00, '2024-09-01', 'installed'),
('ORD2025001', 2, 2, 40,  305.00, 12200.00, '2025-01-12', 'pending');

INSERT INTO installations (device_no, order_id, customer_id, site_name, install_date, warranty_until, location, power_actual_watt) VALUES
('DEV-0001', 1, 1, '濮阳一号电站',  '2024-04-10', '2049-04-10', '河南濮阳', 550),
('DEV-0002', 1, 1, '濮阳一号电站',  '2024-04-10', '2049-04-10', '河南濮阳', 550),
('DEV-0003', 2, 1, '濮阳二号电站',  '2024-07-15', '2049-07-15', '河南濮阳', 575),
('DEV-0004', 3, 2, '北京屋顶电站',  '2024-09-05', '2049-09-05', '北京朝阳', 700),
('DEV-0005', 4, 3, '广州工业园',    '2024-09-20', '2049-09-20', '广州天河', 550);

INSERT INTO service_tickets (ticket_no, installation_id, customer_id, issue_type, description, priority, status, created_at) VALUES
('TK-2024-001', 1, 1, 'warranty',    '组件表面有微小划痕，疑似运输损坏',         'medium', 'resolved',    '2024-06-15 10:00:00'),
('TK-2024-002', 3, 1, 'consultation','询问组件运行功率低于预期是否正常',         'low',    'closed',      '2024-08-20 14:30:00'),
('TK-2024-003', 4, 2, 'repair',      '冬季发电量异常，怀疑接线盒故障',           'high',   'in_progress', '2024-12-05 09:00:00'),
('TK-2024-004', 5, 3, 'inspection',  '年度巡检发现支架锈蚀',                     'medium', 'open',        '2025-01-08 16:00:00');

SELECT '=== tables ===';
SHOW TABLES;
SELECT '=== products count ===';
SELECT COUNT(*) AS product_count FROM products;
SELECT '=== orders count ===';
SELECT COUNT(*) AS order_count FROM orders;
