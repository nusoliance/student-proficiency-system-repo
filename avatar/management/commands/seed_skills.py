from django.core.management.base import BaseCommand
from avatar.models import Course, Skill

COURSES_DATA = {
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
    "BS Computer Engineering": [
        ("Programming", "Writing and debugging code in languages like C and Python, including embedded systems"),
        ("Analytical thinking",
         "Breaking down complex technical problems into solvable parts"),
        ("Circuit design",
         "Building and testing hardware like microcontrollers and PCBs"),
        ("Digital logic design",
         "applying boolean algebra and logic gates to build and analyze digital systems"),
        ("Troubleshooting",
         "Isolating and fixing issues across both hardware and software"),
        ("Algorithm design", "Structuring efficient step-by-step solutions and understanding data structures for problem-solving"),
    ],
    "BS Electrical Engineering": [
        ("Electrical circuit analysis",
         "Computing voltage, current, and power across circuits"),
        ("Power systems design",
         "Designing generation, transmission, and distribution systems"),
        ("Electrical code compliance",
         "Applying the Philippine Electrical Code (PEC) standards"),
        ("Instrumentation and control",
         "Working with sensors, relays, and control systems"),
        ("Technical drafting", "Creating electrical schematics and wiring diagrams"),
        ("Load calculation",
         "Determining power requirements and sizing for electrical systems"),
    ],
    "BS Electronics Engineering": [
        ("Analog circuit design",
         "Designing amplifiers, filters, and analog signal circuits"),
        ("Signal processing", "Analyzing and manipulating audio, RF, or digital signals"),
        ("Microcontroller programming",
         "Writing embedded code for microprocessors and microcontrollers"),
        ("Communications systems design",
         "Designing systems for transmitting and receiving signals"),
        ("PCB design", "Laying out and prototyping printed circuit boards"),
        ("Systems testing",
         "Verifying that electronic systems function within required specs"),
    ],
    "BS Mechanical Engineering": [
        ("Thermodynamics application",
         "Applying heat and energy principles to mechanical systems"),
        ("Machine design", "Designing mechanical components and assemblies"),
        ("Materials science",
         "Understanding material properties and behavior for engineering use"),
        ("Manufacturing processes",
         "Understanding machining, welding, casting, and fabrication methods"),
        ("Fluid mechanics",
         "Analyzing the behavior of liquids and gases in mechanical systems"),
        ("Kinematics analysis", "Analyzing motion, forces, and mechanisms in machines"),
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
        self.stdout.write(self.style.SUCCESS("Done seeding skills!"))
