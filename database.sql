-- SkillSphere AI Database
-- Run this once to create the schema and seed sample data.

CREATE DATABASE IF NOT EXISTS skillsphere;
USE skillsphere;

-- ========== USERS ==========
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'Learner',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========== COURSES ==========
CREATE TABLE IF NOT EXISTS courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    type VARCHAR(20) DEFAULT 'Video',
    duration VARCHAR(50) DEFAULT '1 week',
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========== ENROLLMENTS ==========
CREATE TABLE IF NOT EXISTS enrollments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT NOT NULL,
    progress INT DEFAULT 0,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- ========== ASSESSMENTS ==========
CREATE TABLE IF NOT EXISTS assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT,
    score INT DEFAULT 0,
    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ========== CERTIFICATES ==========
CREATE TABLE IF NOT EXISTS certificates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT NOT NULL,
    certificate_id VARCHAR(50) NOT NULL UNIQUE,
    date DATE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- ========== SKILLS ==========
CREATE TABLE IF NOT EXISTS skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    score INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ========== DISCUSSIONS ==========
CREATE TABLE IF NOT EXISTS discussions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ========== SAMPLE DATA ==========

INSERT INTO courses (title, description, type, duration) VALUES
('Python for Beginners', 'Learn Python programming from scratch with hands-on exercises.', 'Video', '2 weeks'),
('SQL Fundamentals', 'Master database queries and relational design.', 'Video', '10 days'),
('Machine Learning Basics', 'Introduction to supervised and unsupervised learning.', 'Video', '3 weeks'),
('Cloud Computing 101', 'Understand cloud platforms, deployment and scaling.', 'PDF', '1 week'),
('Data Structures & Algorithms', 'Core CS concepts for technical interviews.', 'Assignment', '4 weeks'),
('AI Ethics & Governance', 'Responsible AI development and deployment practices.', 'PDF', '5 days');

-- Demo user (password is "password123" hashed with werkzeug - replace after first run if needed)
-- Skills and enrollments seeded once a real user registers; kept minimal here.
