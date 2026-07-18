from django.core.management.base import BaseCommand
from avatar.models import Course, Skill

COURSES_DATA = {
    "Bachelor of Elementary Education": [
        ("Communication skills",
         "Explaining concepts clearly and adjusting language to a young learner's level"),
        ("Classroom management",
         "Keeping a room of children focused, orderly, and on task"),
        ("Lesson planning",
         "Structuring lessons with clear objectives, activities, and pacing"),
        ("Differentiated instruction",
         "Adjusting teaching methods to fit different learning speeds and styles"),
        ("Creativity", "Designing engaging visual aids, games, and activities to hold attention"),
        ("Assessment skills",
         "Creating and interpreting tests/quizzes that fairly measure learning"),
    ],
    "BS Civil Engineering": [
        ("Mathematical skills",
         "Applying calculus and structural formulas to analyze loads and designs"),
        ("CAD proficiency", "Using AutoCAD/Revit to draft and visualize construction plans"),
        ("Problem-solving", "Working through design or construction issues methodically"),
        ("Project management", "Planning budgets, timelines, and coordinating work phases"),
        ("Building code knowledge",
         "Applying the National Structural Code of the Philippines (NSCP) and local regulations correctly"),
        ("Attention to detail",
         "Ensuring measurements and specifications are precise, since small errors are costly"),
    ],
    "BS Nursing": [
        ("Clinical judgment", "Reading patient symptoms and making sound care decisions"),
        ("Communication", "Relaying information clearly between patients, families, and medical staff"),
        ("Documentation and charting",
         "Accurately recording patient data and treatment history"),
        ("Attention to detail",
         "Administering correct dosages and following exact procedures"),
        ("Time management", "Prioritizing and handling multiple patients efficiently"),
        ("Manual dexterity",
         "Performing hands-on procedures like IVs, injections, and wound care"),
    ],
    "BS Computer Engineering": [
        ("Programming", "Writing and debugging code in languages like C and Python, including embedded systems"),
        ("Analytical thinking",
         "Breaking down complex technical problems into solvable parts"),
        ("Circuit design", "Building and testing hardware like microcontrollers and PCBs"),
        ("Mathematical skills",
         "Applying discrete math, calculus, and digital logic to engineering problems"),
        ("Troubleshooting", "Isolating and fixing issues across both hardware and software"),
        ("Algorithm design", "Structuring efficient step-by-step solutions and understanding data structures for problem-solving"),
    ],
}

GENERAL_SKILLS = [
    ("Communication skills", "Expressing ideas clearly in speech and writing"),
    ("Time management", "Organizing tasks and meeting deadlines effectively"),
    ("Critical thinking", "Analyzing information and reasoning through problems logically"),
    ("Self-discipline", "Staying consistent with study habits and responsibilities"),
    ("Adaptability", "Adjusting to new situations, methods, or unexpected challenges"),
    ("Collaboration", "Working productively with others toward a shared goal"),
]


class Command(BaseCommand):
    help = 'Seeds courses and their related skills, plus general education and broad skills'

    def handle(self, *args, **options):
        for course_name, skills in COURSES_DATA.items():
            course, _ = Course.objects.get_or_create(name=course_name)
            for skill_name, description in skills:
                Skill.objects.get_or_create(
                    name=skill_name, course=course,
                    defaults={'description': description, 'category': 'course'}
                )
            self.stdout.write(self.style.SUCCESS(
                f"Seeded course: {course_name}"))

        for skill_name, description in GENERAL_SKILLS:
            Skill.objects.get_or_create(
                name=skill_name, course=None, category='general',
                defaults={'description': description}
            )
        self.stdout.write(self.style.SUCCESS(
            "Seeded general education skills"))

        Skill.objects.get_or_create(
            name="General Proficiency", course=None, category='broad',
            defaults={
                'description': 'A broad skill for students not enrolled in a specific college course'}
        )
        self.stdout.write(self.style.SUCCESS("Seeded broad skill"))
        self.stdout.write(self.style.SUCCESS("Done seeding skills!"))
