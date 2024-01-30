from protohaven_api.class_automation.solver import Class, Person, solve


def test_solve():
    classes = [
        Class(*v)
        for v in [
            ("Embroidery", 1, "textiles", 0.7),
            ("Sewing Basics", 2, "textiles", 0.6),
            ("Basic Woodshop", 2, "wood", 0.5),
            ("Millwork", 1, "wood", 0.7),
            ("Basic Metals", 2, "metal", 0.8),
            ("Metal Workshop", 1, "metal", 0.4),
        ]
    ]

    people = [
        Person(*v)
        for v in [
            ("A", ["Embroidery", "Sewing Basics"], 6, [1, 7, 14, 21, 29]),
            (
                "B",
                ["Basic Woodshop", "Embroidery", "Millwork"],
                4,
                [1, 4, 5, 8, 11, 14, 22, 25, 29],
            ),
            ("C", ["Basic Metals", "Metal Workshop", "Embroidery"], 2, [5, 7, 2, 1]),
            ("D", ["Millwork", "Sewing Basics"], 1, list(range(30))),
        ]
    ]

    (schedule, load, score) = solve(classes, people)
