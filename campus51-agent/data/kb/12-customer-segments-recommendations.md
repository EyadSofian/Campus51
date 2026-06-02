# Campus 51 — Customer Segments & Recommendation Playbook

This document maps user types to recommended courses and pathways. The bot uses it to make focused, relevant recommendations.

---

## Segment 1: B2B — School Owners & Directors

**Profile:** Decision-makers responsible for staff development, school accreditation, and institutional quality.

**Pain points:**
- Need to upskill entire teaching staff cost-effectively.
- Seeking international accreditation for the school.
- Want measurable impact on teaching quality.
- Need flexible delivery that doesn't disrupt school operations.

**Best-fit offerings:**
- **Custom packages** with group pricing.
- **Partnership tracks** (white-label, co-certification).
- **Educational Leadership** course for the leadership team.
- **Six Levers for Elevating Middle Leadership** for HODs.
- **Coaching & Mentoring in Education** for building a coaching culture.
- **Diversity & Inclusion** + **Safeguarding** for school-wide compliance.

**Bot action:** Always route to consultation — these decisions are not made in chat.

---

## Segment 2: B2B — Principals & Vice-Principals

**Profile:** Operational school leaders implementing professional development plans.

**Pain points:**
- Building leadership capacity in middle management.
- Improving instructional quality.
- Managing change initiatives.

**Best-fit offerings:**
- **Educational Leadership**
- **Six Levers for Elevating Middle Leadership**
- **Teachers as Researchers**
- **Coaching & Mentoring in Education**
- **AI Revolution in Education** (strategic planning)

---

## Segment 3: B2B — HODs / Subject Coordinators

**Profile:** Middle leaders bridging senior leadership and teaching teams.

**Pain points:**
- Leading curriculum decisions in their subject area.
- Coaching teachers in their department.
- Managing performance and observations.

**Best-fit offerings:**
- **Six Levers for Elevating Middle Leadership**
- **Curriculum Mapping for Impact & Alignment**
- **Coaching & Mentoring in Education**
- **Assessment & Feedback**
- Subject-specific courses (ELT, STEAM, ABA, etc.) based on their department.

---

## Segment 4: B2C — Early-Career K-12 Teachers

**Profile:** Teachers with 0-3 years experience, often without formal teaching qualification.

**Pain points:**
- Building foundational pedagogical knowledge.
- Seeking professional recognition / certification.
- Career progression in international schools.

**Best-fit pathways:**
- **QTS Pathway** (the flagship recommendation for this segment).
- **Approaches to Teaching & Learning**
- **Active Learning in the 21st Century Classroom**
- **Applying Bloom's Taxonomy in Daily Lessons**
- **Positive Discipline in Action**
- **Social-Emotional Learning**
- **Preparing for TKT** (for ELT teachers).

**Bot action:** Lead with QTS pathway for unqualified teachers; lead with TKT for ELT teachers.

---

## Segment 5: B2C — Experienced K-12 Teachers (3+ years)

**Profile:** Teachers building toward leadership or specialization.

**Pain points:**
- Specializing in a subject area or methodology.
- Moving into HOD or coaching roles.
- Internationally certified credentials.

**Best-fit offerings:**
- **DELTA** (for experienced ELT teachers).
- **Teachers as Researchers** (action research, MA prep).
- **Coaching & Mentoring in Education**.
- **AI Tools in Classroom Practice** (modern upskill).
- **Designing an Authentic Assessment**.

---

## Segment 6: B2C — Subject Specialists

### Math & Science Teachers
- **STEM Simulations in Education**
- **STEAM Foundation**
- **Humanizing Math & Metacognition in Mathematics**
- **Visible Thinking & Routines**
- **Inquiry-Based Learning**

### English Teachers (ELT)
- **Preparing for TKT**
- **DELTA**
- **Teaching English through Drama**
- **Guided Reading in Teaching Language**
- **Balancing the Four Skills**

### Early Years Teachers
- **Understanding Child Development**
- **Effective Routines for Early Learners**
- **Play Skills & Communication**
- **School Readiness**
- **Introduction to Early Detection of Developmental Delays**

### SEN / Shadow Teachers / ABA Practitioners
- **General ABA – Level 1 & 2 (RBT/IBT/QBT)**
- **Foundations of Applied Behavior Analysis**
- **Functions of Behavior**
- **Managing Challenging Behavior**
- **Reinforcement & Pairing**
- **Differentiation for Inclusion**

### EdTech Coordinators / Tech-Curious Teachers
- **AI Revolution in Education**
- **AI Tools in Classroom Practice**
- **Digital Technology in Teaching and Learning**
- **Adaptive Learning**
- **Organizing Blended Learning Models in Practice**

---

## Recommendation Decision Tree

When recommending, the bot follows this priority:

1. **If user is unqualified teacher seeking certification** → recommend **QTS Pathway** first.
2. **If user is ELT teacher seeking certification** → recommend **TKT** (early) or **DELTA** (experienced).
3. **If user is a school decision-maker** → recommend **consultation for custom package**.
4. **If user is HOD/middle leader** → recommend **Six Levers for Middle Leadership**.
5. **If user is subject specialist** → recommend top 2-3 from their subject's list above.
6. **If user is unsure** → ask 1-2 questions to identify segment.

---

## Recommendation Principles

- **Maximum 3 courses per recommendation** — more overwhelms.
- **Maximum 1 strong "next-step" recommendation** per conversation.
- **Always route enrolment to human team** — never quote prices in chat.
- **Match recommendation to user's stated goal**, not random catalog browsing.
- **Build value before naming the course** ("Many ELT teachers in your position pursue X because...").
- **Always end with a soft call-to-action** ("Want me to share more details or connect you with the team?").
