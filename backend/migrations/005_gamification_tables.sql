-- Migration 005: Gamification Session Records and Badges Persistence Tables

CREATE TABLE IF NOT EXISTS `gamification_leaderboard` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `team_name` VARCHAR(255) UNIQUE NOT NULL,
    `instructor_user_id` INT NULL,
    `total_xp` INT DEFAULT 0,
    `level` VARCHAR(100) DEFAULT 'Novice',
    `session_count` INT DEFAULT 0,
    `best_score` FLOAT DEFAULT 0.0,
    `badges` JSON,
    `last_session_at` DATETIME,
    FOREIGN KEY (`instructor_user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `gamification_badges` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `team_name` VARCHAR(255) NOT NULL,
    `badge_id` VARCHAR(100) NOT NULL,
    `session_code` VARCHAR(100) NULL,
    `awarded_at` DATETIME NOT NULL,
    `metadata` JSON NULL,
    UNIQUE KEY `uk_team_badge` (`team_name`, `badge_id`),
    INDEX `idx_team_name` (`team_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `gamification_session_records` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_code` VARCHAR(100) UNIQUE NOT NULL,
    `team_name` VARCHAR(255) NOT NULL,
    `scenario_id` VARCHAR(100) NULL,
    `scenario_name` VARCHAR(255) NULL,
    `difficulty` VARCHAR(50) DEFAULT 'beginner',
    `performance_score` FLOAT DEFAULT 0.0,
    `prediction_accuracy` FLOAT DEFAULT 0.0,
    `grade` VARCHAR(10) DEFAULT 'C',
    `base_xp` INT DEFAULT 200,
    `xp_earned` INT DEFAULT 0,
    `total_xp_after` INT DEFAULT 0,
    `deviation_count` INT DEFAULT 0,
    `critical_misses` JSON NULL,
    `ai_debriefed` BOOLEAN DEFAULT 0,
    `badges_earned` JSON NULL,
    `team_leader` VARCHAR(255) NULL,
    `completed_at` DATETIME NOT NULL,
    INDEX `idx_team_name` (`team_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
