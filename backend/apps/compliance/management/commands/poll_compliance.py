from django.core.management.base import BaseCommand

from apps.compliance.service import poll_all_drivers


class Command(BaseCommand):
    help = (
        "Poll synthetic compliance signals and update Driver.compliance_state. "
        "Revokes dispatch eligibility only — never auto-assigns."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate and print transitions without writing",
        )

    def handle(self, *args, **options):
        summary = poll_all_drivers(dry_run=options["dry_run"])
        self.stdout.write(
            self.style.SUCCESS(
                f"compliance poll checked={summary['checked']} "
                f"changed={summary['changed']} dry_run={summary['dry_run']}"
            )
        )
        for row in summary["results"]:
            if row["changed"] or options["verbosity"] >= 2:
                self.stdout.write(
                    f"  truck={row['truck_id']} {row['from']}→{row['to']} "
                    f"score={row['score']} reasons={row['reasons']}"
                )
