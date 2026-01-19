## 📌 Database Schema — Relationship Summary (Based on Current Models)

**User**  
Primary key: `id`; Related to many `Consultation` records; Also connected to `ConsultAnswer` (optional user response link); Contains flags for admin access and medical history.

**Consultation**  
Primary key: `id`; Foreign keys: `user_id → users.id`, `form_id → consult_forms.id`, `primary_question_id → consult_questions.id`; Connected one-to-many with `ConsultAnswer` and `FollowupAnswers`; Linked one-to-one to its primary `ConsultQuestion`.

**ConsultForm**  
Primary key: `id`; Parent in a one-to-many relationship with `ConsultQuestion`, representing different consultation form templates.

**ConsultQuestion**  
Primary key: `id`; Foreign key: `form_id → consult_forms.id`; Parent in a one-to-many relationship with `FollowupQuestions`; Referenced by `Consultation.primary_question_id` and by `ConsultAnswer.question_id`.

**FollowupQuestions**  
Primary key: `id`; Foreign key: `parent_question_id → consult_questions.id`; Defines conditional follow-up prompts linked to a specific main question.

**ConsultAnswer**  
Primary key: `id`; Foreign keys: `consultation_id → consultations.id`, `user_id → users.id`, `question_id → consult_questions.id`; Represents a user’s answers to the main consultation questions.

**FollowupAnswers**  
Primary key: `id`; Foreign keys: `consultation_id → consultations.id`, `question_id → followup_questions.id`; Stores answers to follow-up questions, including optional file paths for uploaded images.

User (1) —— (M) Consultation (1) —— (1) ConsultQuestion
                             │
                             ├── (M) ConsultAnswer
                             │
                             └── (M) FollowupAnswers —— (1) FollowupQuestions —— (M) ConsultQuestion
