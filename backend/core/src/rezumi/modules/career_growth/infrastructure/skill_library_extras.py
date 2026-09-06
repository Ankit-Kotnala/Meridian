"""Additional public courses and official docs layered onto family packs.

These URLs are official platform or documentation pages, not a scrape of another
roadmap site and not a copy of a paid curriculum.
"""

from __future__ import annotations

from urllib.parse import quote_plus

Resource = tuple[str, str, str]


def _hit(key: str, needle: str) -> bool:
    token = needle.casefold()
    if any(character in token for character in " /-"):
        return token in key
    return f" {token} " in f" {key} " or key.startswith(f"{token} ") or key.endswith(f" {token}")


def _yt(title: str, provider: str, video_id: str) -> Resource:
    return (title, provider, f"https://www.youtube.com/watch?v={video_id}")


def skill_discovery(name: str) -> tuple[tuple[Resource, ...], tuple[Resource, ...]]:
    q = quote_plus(name)
    free = (
        (
            f"{name} complete courses on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+complete+course",
        ),
        (
            f"{name} playlists on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+playlist",
        ),
        (
            f"{name} university lectures on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+university+lecture",
        ),
        (
            f"{name} tutorials for beginners on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+tutorial+for+beginners",
        ),
        (
            f"{name} interview walkthroughs on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+interview+questions",
        ),
        (
            f"{name} workshops on YouTube",
            "YouTube",
            f"https://www.youtube.com/results?search_query={q}+workshop",
        ),
        (
            f"{name} repositories on GitHub",
            "GitHub",
            f"https://github.com/search?q={q}&type=repositories",
        ),
        (
            f"{name} on Google Developers",
            "Google Developers",
            f"https://developers.google.com/s/results?q={q}",
        ),
        (
            f"{name} on AWS documentation",
            "AWS",
            f"https://docs.aws.amazon.com/search/doc-search.html?searchPath=documentation&searchQuery={q}",
        ),
        (
            f"{name} on Cloudflare learning",
            "Cloudflare",
            f"https://developers.cloudflare.com/search/?q={q}",
        ),
    )
    paid = (
        (
            f"{name} courses on Coursera",
            "Coursera",
            f"https://www.coursera.org/courses?query={q}",
        ),
        (
            f"{name} specializations on Coursera",
            "Coursera",
            f"https://www.coursera.org/search?query={q}&productTypeDescription=Specializations",
        ),
        (
            f"{name} highest-rated on Udemy",
            "Udemy",
            f"https://www.udemy.com/courses/search/?src=ukw&q={q}&sort=highest-rated",
        ),
        (
            f"{name} complete guides on Udemy",
            "Udemy",
            f"https://www.udemy.com/courses/search/?src=ukw&q={q}+complete",
        ),
        (
            f"{name} on LinkedIn Learning",
            "LinkedIn Learning",
            f"https://www.linkedin.com/learning/search?keywords={q}",
        ),
        (
            f"{name} professional certificates on edX",
            "edX",
            f"https://www.edx.org/search?q={q}&content_type=professional-certificate",
        ),
        (
            f"{name} on Google Skillshop",
            "Google Skillshop",
            f"https://skillshop.withgoogle.com/search?query={q}",
        ),
        (
            f"{name} on HubSpot Academy",
            "HubSpot Academy",
            f"https://academy.hubspot.com/courses?q={q}",
        ),
    )
    return free, paid


def family_bonus(family: str) -> tuple[tuple[Resource, ...], tuple[Resource, ...]]:
    lane = "tech" if family in _TECH_FAMILIES else "business"
    shared_free, shared_paid = _SHARED[lane]
    bonus = _FAMILY_BONUS.get(family, _FAMILY_BONUS["product"])
    return (*shared_free, *bonus[0]), (*shared_paid, *bonus[1])


def keyword_bonus(name: str) -> tuple[tuple[Resource, ...], tuple[Resource, ...]]:
    key = name.casefold()
    free: list[Resource] = []
    paid: list[Resource] = []
    for needles, more_free, more_paid in _KEYWORD_PACKS:
        if any(_hit(key, needle) for needle in needles):
            free.extend(more_free)
            paid.extend(more_paid)
    return tuple(free), tuple(paid)


_TECH_FAMILIES = frozenset(
    {
        "algorithms",
        "git",
        "testing",
        "system_design",
        "distributed",
        "frontend",
        "javascript",
        "accessibility",
        "databases",
        "python",
        "ml",
        "llm",
        "data",
        "statistics",
        "devops",
        "linux",
        "cloud",
        "security",
        "mobile",
        "networking",
        "architecture",
        "qa",
    }
)

_SHARED: dict[str, tuple[tuple[Resource, ...], tuple[Resource, ...]]] = {
    "tech": (
        (
            _yt(
                "Harvard CS50 2023 — Full course",
                "YouTube / Harvard CS50",
                "8mAITcNt710",
            ),
            (
                "Harvard CS50 lecture notes",
                "Harvard CS50",
                "https://cs50.harvard.edu/x/notes/",
            ),
            (
                "MIT Missing Semester",
                "MIT CSAIL",
                "https://missing.csail.mit.edu/",
            ),
            (
                "freeCodeCamp curriculum",
                "freeCodeCamp",
                "https://www.freecodecamp.org/learn",
            ),
            (
                "The Odin Project",
                "The Odin Project",
                "https://www.theodinproject.com/",
            ),
            (
                "Full Stack Open",
                "University of Helsinki",
                "https://fullstackopen.com/en/",
            ),
            (
                "MDN Learn web development",
                "MDN",
                "https://developer.mozilla.org/en-US/docs/Learn_web_development",
            ),
            ("web.dev Learn", "web.dev", "https://web.dev/learn/"),
            (
                "Microsoft Learn fundamentals browse",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/training/",
            ),
            (
                "Google Developers training",
                "Google Developers",
                "https://developers.google.com/learn",
            ),
        ),
        (
            (
                "Google IT Support Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-it-support",
            ),
            (
                "IBM Full Stack Software Developer",
                "Coursera / IBM",
                "https://www.coursera.org/professional-certificates/ibm-full-stack-software-developer",
            ),
            (
                "Meta Front-End Developer",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/meta-front-end-developer",
            ),
            (
                "Computer Science courses on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=computer+science",
            ),
        ),
    ),
    "business": (
        (
            (
                "Google re:Work guides",
                "Google re:Work",
                "https://rework.withgoogle.com/",
            ),
            (
                "Atlassian Team Playbook",
                "Atlassian",
                "https://www.atlassian.com/team-playbook",
            ),
            (
                "HubSpot Academy",
                "HubSpot Academy",
                "https://academy.hubspot.com/",
            ),
            (
                "Google Skillshop",
                "Google Skillshop",
                "https://skillshop.withgoogle.com/",
            ),
            (
                "PMI learning",
                "PMI",
                "https://www.pmi.org/learning",
            ),
            ("IIBA resources", "IIBA", "https://www.iiba.org/"),
            ("Scrum.org resources", "Scrum.org", "https://www.scrum.org/resources"),
            ("SHRM resources", "SHRM", "https://www.shrm.org/"),
            (
                "Harvard Business Review",
                "HBR",
                "https://hbr.org/",
            ),
            (
                "Manager Tools guidance",
                "Manager Tools",
                "https://www.manager-tools.com/",
            ),
            ("SVPG essays", "SVPG", "https://www.svpg.com/articles/"),
            (
                "Interaction Design Foundation open materials",
                "Interaction Design Foundation",
                "https://www.interaction-design.org/literature",
            ),
        ),
        (
            (
                "Google Project Management Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-project-management",
            ),
            (
                "Google Digital Marketing & E-commerce",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-digital-marketing-ecommerce",
            ),
            (
                "Business foundations on Coursera",
                "Coursera / Wharton",
                "https://www.coursera.org/specializations/wharton-business-foundations",
            ),
            (
                "MBA essentials on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=mba+essentials",
            ),
        ),
    ),
}

_FAMILY_BONUS: dict[str, tuple[tuple[Resource, ...], tuple[Resource, ...]]] = {
    "algorithms": (
        (
            _yt("Abdul Bari — Algorithms", "YouTube / Abdul Bari", "0IAPZzGSbME"),
            _yt("NeetCode — Data Structures", "YouTube / NeetCode", "8h2dF-1lIVU"),
            (
                "Interview University (public notes)",
                "GitHub",
                "https://github.com/jwasham/coding-interview-university",
            ),
            ("LeetCode explore", "LeetCode", "https://leetcode.com/explore/"),
            ("NeetCode roadmap", "NeetCode", "https://neetcode.io/roadmap"),
            (
                "MIT 6.006 on OCW",
                "MIT OCW",
                "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/",
            ),
        ),
        (
            (
                "Algorithms, Part II",
                "Coursera / Princeton",
                "https://www.coursera.org/learn/algorithms-part2",
            ),
            (
                "Master the Coding Interview on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=master+the+coding+interview",
            ),
        ),
    ),
    "git": (
        (
            _yt("Git intern internals", "YouTube / Fireship", "hwP7WQkmECE"),
            (
                "GitHub Git handbook",
                "GitHub",
                "https://docs.github.com/en/get-started/using-git/about-git",
            ),
            (
                "Learn Git branching (hosted docs)",
                "GitHub",
                "https://github.com/pcottle/learnGitBranching",
            ),
        ),
        (
            (
                "GitHub Actions on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=github%20actions",
            ),
        ),
    ),
    "testing": (
        (
            ("Jest documentation", "Jest", "https://jestjs.io/docs/getting-started"),
            ("pytest documentation", "pytest", "https://docs.pytest.org/en/stable/"),
            _yt("Playwright crash course", "YouTube / Playwright", "5nNUo0P2KaU"),
        ),
        (
            (
                "Automated testing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=playwright+automation",
            ),
        ),
    ),
    "system_design": (
        (
            _yt(
                "System Design for Beginners — Full Course",
                "YouTube / freeCodeCamp",
                "mtyT6I69zwU",
            ),
            _yt("System Design Primer lecture", "YouTube / Gaurav Sen", "SqcXvc3ZapM"),
            (
                "System Design Primer",
                "GitHub",
                "https://github.com/donnemartin/system-design-primer",
            ),
            ("AWS Architecture Center", "AWS", "https://aws.amazon.com/architecture/"),
        ),
        (
            (
                "Cloud architecture on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=system%20design",
            ),
        ),
    ),
    "distributed": (
        (
            (
                "Google SRE book",
                "Google SRE",
                "https://sre.google/sre-book/table-of-contents/",
            ),
            (
                "Apache Kafka documentation",
                "Apache Kafka",
                "https://kafka.apache.org/documentation/",
            ),
            ("RabbitMQ tutorials", "RabbitMQ", "https://www.rabbitmq.com/tutorials"),
            ("Redis documentation", "Redis", "https://redis.io/docs/latest/"),
        ),
        (
            (
                "Cloud Computing Specialization",
                "Coursera / University of Illinois",
                "https://www.coursera.org/specializations/cloud-computing",
            ),
        ),
    ),
    "frontend": (
        (
            _yt("HTML Full Course — Build a Website", "YouTube / SuperSimpleDev", "G3e-kaEnCyM"),
            _yt("CSS Tutorial — Full Course", "YouTube / freeCodeCamp", "OXGznpTZVsk"),
            ("web.dev CSS", "web.dev", "https://web.dev/learn/css/"),
            ("web.dev HTML", "web.dev", "https://web.dev/learn/html/"),
        ),
        (
            (
                "Advanced CSS on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=advanced+css",
            ),
        ),
    ),
    "javascript": (
        (
            _yt(
                "JavaScript Tutorial for Beginners — Full Course",
                "YouTube / freeCodeCamp",
                "jS4aFq5-91M",
            ),
            _yt(
                "TypeScript Course for Beginners",
                "YouTube / freeCodeCamp",
                "30LWjhZzg50",
            ),
            ("JavaScript.info", "javascript.info", "https://javascript.info/"),
            (
                "TypeScript handbook",
                "TypeScript",
                "https://www.typescriptlang.org/docs/handbook/intro.html",
            ),
            ("React documentation", "React", "https://react.dev/learn"),
            ("Next.js learn", "Next.js", "https://nextjs.org/learn"),
        ),
        (
            (
                "Meta React Native / React on Coursera",
                "Coursera / Meta",
                "https://www.coursera.org/search?query=react",
            ),
        ),
    ),
    "accessibility": (
        (
            ("W3C WAI tutorials", "W3C", "https://www.w3.org/WAI/tutorials/"),
            ("WebAIM articles", "WebAIM", "https://webaim.org/articles/"),
            ("The A11Y Project", "A11Y Project", "https://www.a11yproject.com/"),
            ("web.dev accessibility", "web.dev", "https://web.dev/learn/accessibility/"),
        ),
        (
            (
                "Accessible web design on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=web%20accessibility",
            ),
        ),
    ),
    "databases": (
        (
            _yt(
                "SQL Tutorial — Full Database Course for Beginners",
                "YouTube / freeCodeCamp",
                "HXV3zeQKqGY",
            ),
            _yt(
                "PostgreSQL Tutorial for Beginners",
                "YouTube / freeCodeCamp",
                "qw--VYLpxG4",
            ),
            (
                "PostgreSQL documentation",
                "PostgreSQL",
                "https://www.postgresql.org/docs/current/",
            ),
            ("Use The Index, Luke", "Use The Index, Luke", "https://use-the-index-luke.com/"),
            ("Kaggle Intro to SQL", "Kaggle", "https://www.kaggle.com/learn/intro-to-sql"),
        ),
        (
            (
                "Databases and SQL for Data Science",
                "Coursera / IBM",
                "https://www.coursera.org/learn/sql-data-science",
            ),
        ),
    ),
    "python": (
        (
            _yt("Python for Everybody — Full Course", "YouTube / freeCodeCamp", "8DvywoWv6fI"),
            _yt("Python tutorial — 4 hours", "YouTube / Programming with Mosh", "kqtD5dpn9C8"),
            (
                "Python tutorial",
                "Python.org",
                "https://docs.python.org/3/tutorial/index.html",
            ),
            ("Real Python-adjacent official FAQ", "Python.org", "https://docs.python.org/3/faq/"),
        ),
        (
            (
                "Python for Everybody Specialization",
                "Coursera / University of Michigan",
                "https://www.coursera.org/specializations/python",
            ),
        ),
    ),
    "ml": (
        (
            _yt("Machine Learning for Everybody", "YouTube / freeCodeCamp", "i_LwzRVP7bg"),
            _yt("Neural networks — 3Blue1Brown", "YouTube / 3Blue1Brown", "aircAruvnKk"),
            ("fast.ai Practical Deep Learning", "fast.ai", "https://course.fast.ai/"),
            ("Kaggle Learn", "Kaggle", "https://www.kaggle.com/learn"),
            (
                "scikit-learn user guide",
                "scikit-learn",
                "https://scikit-learn.org/stable/user_guide.html",
            ),
            ("PyTorch tutorials", "PyTorch", "https://pytorch.org/tutorials/"),
            ("TensorFlow tutorials", "TensorFlow", "https://www.tensorflow.org/tutorials"),
        ),
        (
            (
                "Machine Learning Specialization",
                "Coursera / DeepLearning.AI",
                "https://www.coursera.org/specializations/machine-learning-introduction",
            ),
            (
                "Deep Learning Specialization",
                "Coursera / DeepLearning.AI",
                "https://www.coursera.org/specializations/deep-learning",
            ),
        ),
    ),
    "llm": (
        (
            (
                "Hugging Face NLP course",
                "Hugging Face",
                "https://huggingface.co/learn/nlp-course/chapter1/1",
            ),
            (
                "Google Generative AI learning path",
                "Google Cloud",
                "https://www.cloudskillsboost.google/",
            ),
            _yt("LangChain / LLM app overview", "YouTube / freeCodeCamp", "lPU6Mnn1j5Q"),
        ),
        (
            (
                "Generative AI with Large Language Models",
                "Coursera / DeepLearning.AI",
                "https://www.coursera.org/learn/generative-ai-with-llms",
            ),
        ),
    ),
    "data": (
        (
            _yt("Data Analysis with Python — Full Course", "YouTube / freeCodeCamp", "r-uOLxNrNk8"),
            ("pandas user guide", "pandas", "https://pandas.pydata.org/docs/user_guide/index.html"),
            ("Kaggle pandas course", "Kaggle", "https://www.kaggle.com/learn/pandas"),
            (
                "Google Analytics Academy",
                "Google Skillshop",
                "https://skillshop.withgoogle.com/analytics",
            ),
        ),
        (
            (
                "Google Data Analytics Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-data-analytics",
            ),
            (
                "IBM Data Analyst",
                "Coursera / IBM",
                "https://www.coursera.org/professional-certificates/ibm-data-analyst",
            ),
        ),
    ),
    "statistics": (
        (
            (
                "Khan Academy statistics and probability",
                "Khan Academy",
                "https://www.khanacademy.org/math/statistics-probability",
            ),
            _yt("Statistics — Full Course", "YouTube / freeCodeCamp", "xxpc-HPKN68"),
            (
                "MIT 18.05 OCW",
                "MIT OCW",
                "https://ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2022/",
            ),
        ),
        (
            (
                "Statistics with Python Specialization",
                "Coursera / University of Michigan",
                "https://www.coursera.org/specializations/statistics-with-python",
            ),
        ),
    ),
    "devops": (
        (
            _yt("Docker Tutorial for Beginners", "YouTube / freeCodeCamp", "3c-iBn73dDE"),
            _yt("Kubernetes Course — Full Course", "YouTube / freeCodeCamp", "d6WC5n9G_sM"),
            ("Docker documentation", "Docker", "https://docs.docker.com/get-started/"),
            ("Kubernetes documentation", "Kubernetes", "https://kubernetes.io/docs/home/"),
            (
                "HashiCorp Terraform tutorials",
                "HashiCorp",
                "https://developer.hashicorp.com/terraform/tutorials",
            ),
            ("Grafana tutorials", "Grafana", "https://grafana.com/tutorials/"),
            (
                "Prometheus documentation",
                "Prometheus",
                "https://prometheus.io/docs/introduction/overview/",
            ),
        ),
        (
            (
                "DevOps on AWS Specialization",
                "Coursera / Amazon",
                "https://www.coursera.org/specializations/aws-devops",
            ),
            (
                "Kubernetes on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=certified+kubernetes",
            ),
        ),
    ),
    "linux": (
        (
            _yt("Linux for Beginners — Full Course", "YouTube / freeCodeCamp", "sWbYiFdhhKI"),
            (
                "Ubuntu server guide",
                "Ubuntu",
                "https://ubuntu.com/server/docs",
            ),
            ("Linux man-pages", "man7.org", "https://man7.org/linux/man-pages/"),
        ),
        (
            (
                "Linux on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=linux",
            ),
        ),
    ),
    "cloud": (
        (
            (
                "AWS Skill Builder free digital training",
                "AWS",
                "https://skillbuilder.aws/",
            ),
            (
                "Google Cloud skills boost",
                "Google Cloud",
                "https://www.cloudskillsboost.google/",
            ),
            (
                "Microsoft Learn Azure fundamentals",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/training/paths/azure-fundamentals/",
            ),
            _yt(
                "AWS Certified Cloud Practitioner — Full Course",
                "YouTube / freeCodeCamp",
                "SOTamWNgDKc",
            ),
        ),
        (
            (
                "AWS Cloud Solutions Architect",
                "Coursera / Amazon",
                "https://www.coursera.org/professional-certificates/aws-cloud-solutions-architect",
            ),
        ),
    ),
    "security": (
        (
            ("OWASP Top 10", "OWASP", "https://owasp.org/www-project-top-ten/"),
            (
                "OWASP Cheat Sheet Series",
                "OWASP",
                "https://cheatsheetseries.owasp.org/",
            ),
            (
                "PortSwigger Web Security Academy",
                "PortSwigger",
                "https://portswigger.net/web-security",
            ),
            ("MITRE ATT&CK", "MITRE", "https://attack.mitre.org/"),
            ("CWE list", "MITRE", "https://cwe.mitre.org/"),
            _yt("Ethical Hacking — Full Course", "YouTube / freeCodeCamp", "3Kq1MIfTWCE"),
        ),
        (
            (
                "IBM Cybersecurity Analyst",
                "Coursera / IBM",
                "https://www.coursera.org/professional-certificates/ibm-cybersecurity-analyst",
            ),
            (
                "Google Cybersecurity Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-cybersecurity",
            ),
        ),
    ),
    "mobile": (
        (
            (
                "Android developer docs",
                "Android",
                "https://developer.android.com/courses",
            ),
            (
                "Apple developer documentation",
                "Apple",
                "https://developer.apple.com/documentation/",
            ),
            _yt("Flutter Course for Beginners", "YouTube / freeCodeCamp", "VPvVD0tPx4Y"),
        ),
        (
            (
                "Meta Android Developer",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/meta-android-developer",
            ),
            (
                "Meta iOS Developer",
                "Coursera / Meta",
                "https://www.coursera.org/professional-certificates/meta-ios-developer",
            ),
        ),
    ),
    "networking": (
        (
            _yt("Computer Networking Course", "YouTube / freeCodeCamp", "qiQR5rTSshw"),
            (
                "Cloudflare Learning Center",
                "Cloudflare",
                "https://www.cloudflare.com/learning/",
            ),
            ("RFC editor search", "RFC Editor", "https://www.rfc-editor.org/search/rfc_search.php"),
        ),
        (
            (
                "Computer Communications Specialization",
                "Coursera / University of Colorado",
                "https://www.coursera.org/specializations/computer-communications",
            ),
        ),
    ),
    "architecture": (
        (
            (
                "Microsoft Azure Architecture Center",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/azure/architecture/",
            ),
            ("CNCF projects", "CNCF", "https://www.cncf.io/projects/"),
            ("Thoughtworks Radar", "Thoughtworks", "https://www.thoughtworks.com/radar"),
        ),
        (
            (
                "Software Architecture on Coursera",
                "Coursera / University of Alberta",
                "https://www.coursera.org/specializations/software-design-architecture",
            ),
        ),
    ),
    "qa": (
        (
            (
                "Ministry of Testing articles",
                "Ministry of Testing",
                "https://www.ministryoftesting.com/articles",
            ),
            _yt("Software Testing Tutorial", "YouTube / freeCodeCamp", "u6QfIXgjwGQ"),
        ),
        (
            (
                "Software testing on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=software+testing+istqb",
            ),
        ),
    ),
    "product": (
        (
            ("SVPG product essays", "SVPG", "https://www.svpg.com/articles/"),
            (
                "Reforge insights (public articles)",
                "Reforge",
                "https://www.reforge.com/blog",
            ),
            _yt("Product Management — Full Course", "YouTube / freeCodeCamp", "CJep_UYSFvI"),
        ),
        (
            (
                "Digital Product Management",
                "Coursera / University of Virginia",
                "https://www.coursera.org/specializations/digital-product-management",
            ),
        ),
    ),
    "design": (
        (
            ("Figma learn", "Figma", "https://help.figma.com/hc/en-us/categories/360002042553"),
            ("Material Design", "Google", "https://m3.material.io/"),
            ("Nielsen Norman Group articles", "NN/g", "https://www.nngroup.com/articles/"),
            _yt("UI/UX Design Course", "YouTube / freeCodeCamp", "c9Wg6Cb_YlU"),
        ),
        (
            (
                "Google UX Design Professional Certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-ux-design",
            ),
        ),
    ),
    "research": (
        (
            (
                "NN/g user research",
                "NN/g",
                "https://www.nngroup.com/topic/user-testing/",
            ),
            (
                "Interaction Design research literature",
                "Interaction Design Foundation",
                "https://www.interaction-design.org/literature/topics/user-research",
            ),
        ),
        (
            (
                "User research on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=user%20research",
            ),
        ),
    ),
    "management": (
        (
            (
                "Google re:Work managers",
                "Google re:Work",
                "https://rework.withgoogle.com/en/guides/managers-identify-what-makes-a-great-manager",
            ),
            _yt("Engineering management talks", "YouTube", "rYl_JYJFQio"),
        ),
        (
            (
                "Leading People and Teams",
                "Coursera / University of Michigan",
                "https://www.coursera.org/specializations/leading-people-teams",
            ),
        ),
    ),
    "business_analysis": (
        (
            (
                "IIBA knowledge resources",
                "IIBA",
                "https://www.iiba.org/business-analysis-resources/",
            ),
            (
                "Atlassian requirement playbooks",
                "Atlassian",
                "https://www.atlassian.com/software/confluence/templates/category/product-management",
            ),
        ),
        (
            (
                "Business analysis on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=business+analysis",
            ),
        ),
    ),
    "writing": (
        (
            (
                "The Good Docs Project",
                "The Good Docs Project",
                "https://www.thegooddocsproject.dev/",
            ),
            (
                "Google developer documentation style guide",
                "Google Developers",
                "https://developers.google.com/style",
            ),
            (
                "Microsoft Writing Style Guide",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/style-guide/welcome/",
            ),
        ),
        (
            (
                "Technical writing on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=technical%20writing",
            ),
        ),
    ),
    "project": (
        (
            (
                "Atlassian project management",
                "Atlassian",
                "https://www.atlassian.com/work-management/project-management",
            ),
            ("PMI project topics", "PMI", "https://www.pmi.org/learning/library"),
        ),
        (
            (
                "Google Project Management",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-project-management",
            ),
        ),
    ),
    "agile": (
        (
            ("Scrum Guide (Scrum.org)", "Scrum.org", "https://www.scrum.org/resources/scrum-guide"),
            (
                "Atlassian Agile Coach",
                "Atlassian",
                "https://www.atlassian.com/agile",
            ),
            (
                "Agile Alliance resources",
                "Agile Alliance",
                "https://www.agilealliance.org/agile101/",
            ),
        ),
        (
            (
                "Agile on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=agile%20scrum",
            ),
        ),
    ),
    "support": (
        (
            (
                "Google IT Support materials",
                "Google",
                "https://grow.google/certificates/it-support/",
            ),
            (
                "Microsoft Learn troubleshooting",
                "Microsoft Learn",
                "https://learn.microsoft.com/en-us/training/paths/describe-basics-of-security-compliance-identity/",
            ),
        ),
        (
            (
                "IT support on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=it+support",
            ),
        ),
    ),
    "sales": (
        (
            (
                "HubSpot sales training",
                "HubSpot Academy",
                "https://academy.hubspot.com/courses/sales",
            ),
            ("Gong resources", "Gong", "https://www.gong.io/resources/"),
            (
                "Salesforce Trailhead sales",
                "Salesforce",
                "https://trailhead.salesforce.com/en/content/learn/trails/sales",
            ),
        ),
        (
            (
                "Sales training on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=sales",
            ),
        ),
    ),
    "marketing": (
        (
            ("Moz Beginner's Guide to SEO", "Moz", "https://moz.com/beginners-guide-to-seo"),
            (
                "Google SEO Starter Guide",
                "Google Developers",
                "https://developers.google.com/search/docs/fundamentals/seo-starter-guide",
            ),
            (
                "HubSpot inbound marketing",
                "HubSpot Academy",
                "https://academy.hubspot.com/courses/inbound-marketing",
            ),
            (
                "Meta Blueprint",
                "Meta Blueprint",
                "https://www.facebookblueprint.com/",
            ),
        ),
        (
            (
                "Google Digital Marketing certificate",
                "Coursera / Google",
                "https://www.coursera.org/professional-certificates/google-digital-marketing-ecommerce",
            ),
        ),
    ),
    "finance": (
        (
            (
                "Khan Academy finance and capital markets",
                "Khan Academy",
                "https://www.khanacademy.org/economics-finance-domain/core-finance",
            ),
            (
                "Investor.gov",
                "SEC Investor.gov",
                "https://www.investor.gov/",
            ),
            ("Investopedia academy articles", "Investopedia", "https://www.investopedia.com/"),
        ),
        (
            (
                "Financial Markets (Yale)",
                "Coursera / Yale",
                "https://www.coursera.org/learn/financial-markets-global",
            ),
        ),
    ),
    "accounting": (
        (
            (
                "IFRS educational materials",
                "IFRS",
                "https://www.ifrs.org/issued-standards/ifrs-accounting-standards/",
            ),
            _yt("Accounting Basics — Full Course", "YouTube / freeCodeCamp", "yYX4bvQSqbo"),
        ),
        (
            (
                "Intuit Bookkeeping Professional Certificate",
                "Coursera / Intuit",
                "https://www.coursera.org/professional-certificates/intuit-bookkeeping",
            ),
        ),
    ),
    "hr": (
        (
            ("SHRM toolkit", "SHRM", "https://www.shrm.org/topics-tools/tools"),
            ("EEOC guidance", "EEOC", "https://www.eeoc.gov/employers"),
            ("UK GOV employing people", "GOV.UK", "https://www.gov.uk/browse/employing-people"),
        ),
        (
            (
                "Human resource management on Coursera",
                "Coursera",
                "https://www.coursera.org/search?query=human%20resource%20management",
            ),
        ),
    ),
    "recruiting": (
        (
            (
                "LinkedIn Talent Blog",
                "LinkedIn",
                "https://www.linkedin.com/business/talent/blog",
            ),
            (
                "Google re:Work hiring",
                "Google re:Work",
                "https://rework.withgoogle.com/en/subjects/hiring",
            ),
        ),
        (
            (
                "Technical recruiting on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=technical+recruiter",
            ),
        ),
    ),
    "operations": (
        (
            ("ASQ quality resources", "ASQ", "https://asq.org/quality-resources"),
            (
                "MIT OCW operations management",
                "MIT OCW",
                "https://ocw.mit.edu/search/?q=operations%20management",
            ),
        ),
        (
            (
                "Supply Chain Management Specialization",
                "Coursera / Rutgers",
                "https://www.coursera.org/specializations/supply-chain-management",
            ),
        ),
    ),
}

_KEYWORD_PACKS: tuple[tuple[tuple[str, ...], tuple[Resource, ...], tuple[Resource, ...]], ...] = (
    (
        ("data structures", "algorithm"),
        (
            _yt("CS Dojo data structures", "YouTube / CS Dojo", "T9N3mF4z7oI"),
            ("VisuAlgo", "VisuAlgo", "https://visualgo.net/en"),
        ),
        (
            (
                "JavaScript algorithms on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=javascript+algorithms",
            ),
        ),
    ),
    (
        ("sql", "relational", "schema", "query performance", "normalization"),
        (
            _yt("MySQL Tutorial for Beginners", "YouTube / Programming with Mosh", "7S_tz1z_5bA"),
            (
                "PostgreSQL tutorial",
                "PostgreSQL",
                "https://www.postgresql.org/docs/current/tutorial.html",
            ),
        ),
        (
            (
                "The Complete SQL Bootcamp",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=complete+sql+bootcamp",
            ),
        ),
    ),
    (
        ("python",),
        (
            _yt("Intermediate Python", "YouTube / freeCodeCamp", "HGOBQPFzWKo"),
            ("NumPy documentation", "NumPy", "https://numpy.org/doc/stable/"),
        ),
        (
            (
                "Complete Python Bootcamp on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=complete+python+bootcamp",
            ),
        ),
    ),
    (
        ("javascript", "typescript", "component architecture"),
        (
            ("Node.js documentation", "Node.js", "https://nodejs.org/docs/latest/api/"),
            ("Vue.js tutorial", "Vue", "https://vuejs.org/tutorial/"),
            ("Angular documentation", "Angular", "https://angular.dev/tutorials"),
        ),
        (
            (
                "The Complete JavaScript Course on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=complete+javascript+course",
            ),
        ),
    ),
    (
        ("html", "css", "typography", "layout", "brand system"),
        (
            ("MDN CSS", "MDN", "https://developer.mozilla.org/en-US/docs/Web/CSS"),
            ("web.dev performance", "web.dev", "https://web.dev/learn/performance/"),
        ),
        (),
    ),
    (
        (
            "machine learning",
            "deep learning",
            "ml pipeline",
            "model evaluation",
            "model deployment",
            "model serving",
            "model monitoring",
            "drift",
        ),
        (
            ("Keras guides", "Keras", "https://keras.io/guides/"),
            ("DeepLearning.AI", "DeepLearning.AI", "https://www.deeplearning.ai/"),
        ),
        (
            (
                "TensorFlow Developer Certificate prep on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=tensorflow+developer",
            ),
        ),
    ),
    (
        ("llm", "retrieval-augmented", "responsible ai", "prompt"),
        (
            (
                "Hugging Face agents course",
                "Hugging Face",
                "https://huggingface.co/learn/agents-course/unit0/introduction",
            ),
        ),
        (
            (
                "ChatGPT / LLM courses on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=large+language+models",
            ),
        ),
    ),
    (
        ("ci/cd", "infrastructure as code", "monitoring", "incident"),
        (
            (
                "GitHub Actions documentation",
                "GitHub",
                "https://docs.github.com/en/actions",
            ),
            (
                "CNCF projects",
                "CNCF",
                "https://www.cncf.io/projects/",
            ),
        ),
        (),
    ),
    (
        ("cloud", "cost optimization", "core cloud"),
        (
            ("AWS documentation home", "AWS", "https://docs.aws.amazon.com/"),
            (
                "Google Cloud documentation",
                "Google Cloud",
                "https://cloud.google.com/docs",
            ),
        ),
        (),
    ),
    (
        ("vulnerability", "threat", "secure code", "forensics", "owasp"),
        (("CWE Top 25", "MITRE", "https://cwe.mitre.org/top25/"),),
        (),
    ),
    (
        ("seo", "keyword", "link building", "on-page"),
        (
            (
                "Google Search Central",
                "Google Developers",
                "https://developers.google.com/search",
            ),
        ),
        (
            (
                "SEO courses on Udemy",
                "Udemy",
                "https://www.udemy.com/courses/search/?src=ukw&q=seo+training",
            ),
        ),
    ),
    (
        ("figma", "design system", "interaction design", "microcopy"),
        (("Figma developers", "Figma", "https://www.figma.com/developers"),),
        (),
    ),
    (
        ("financial", "valuation", "modeling"),
        (
            (
                "Khan Academy valuation and investing",
                "Khan Academy",
                "https://www.khanacademy.org/economics-finance-domain/core-finance/stock-and-bonds",
            ),
        ),
        (),
    ),
)
