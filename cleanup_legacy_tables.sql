-- =============================================
-- 🧹 LoanMVP Database Cleanup Script
-- Removes legacy tables & constraints that cause
-- migration or dependency conflicts
-- =============================================

\c loanmvp_db;

-- Disable foreign key checks temporarily
SET session_replication_role = replica;

-- Drop legacy or duplicate tables if they exist
DROP TABLE IF EXISTS borrower CASCADE;
DROP TABLE IF EXISTS notes CASCADE;
DROP TABLE IF EXISTS lead CASCADE;
DROP TABLE IF EXISTS message CASCADE;
DROP TABLE IF EXISTS loan_quote CASCADE;
DROP TABLE IF EXISTS property_analysis CASCADE;
DROP TABLE IF EXISTS lender_quote CASCADE;
DROP TABLE IF EXISTS loan_officer_ai_summary CASCADE;
DROP TABLE IF EXISTS loan_officer_profile CASCADE;
DROP TABLE IF EXISTS loan_officer_portfolio CASCADE;
DROP TABLE IF EXISTS loan_officer_analytics CASCADE;
DROP TABLE IF EXISTS subscription_plan CASCADE;
DROP TABLE IF EXISTS behavioral_insights CASCADE;
DROP TABLE IF EXISTS loan_application CASCADE;
DROP TABLE IF EXISTS credit_profile CASCADE;
DROP TABLE IF EXISTS project_budget CASCADE;
DROP TABLE IF EXISTS loan_document CASCADE;
DROP TABLE IF EXISTS property CASCADE;

-- Re-enable foreign key checks
SET session_replication_role = DEFAULT;

-- Confirmation message
SELECT '✅ Legacy LoanMVP tables cleaned successfully.' AS status;
