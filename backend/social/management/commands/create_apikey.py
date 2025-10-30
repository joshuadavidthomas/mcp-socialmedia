"""Management command to create API keys"""
from django.core.management.base import BaseCommand, CommandError
from social.models import Team, ApiKey


class Command(BaseCommand):
    help = 'Create a new API key for a team'

    def add_arguments(self, parser):
        parser.add_argument(
            'team_name',
            type=str,
            help='Name of the team'
        )
        parser.add_argument(
            '--name',
            type=str,
            required=True,
            help='Friendly name for the API key'
        )
        parser.add_argument(
            '--create-team',
            action='store_true',
            help='Create the team if it does not exist'
        )

    def handle(self, *args, **options):
        team_name = options['team_name']
        key_name = options['name']
        create_team = options['create_team']

        # Get or create team
        if create_team:
            team, created = Team.objects.get_or_create(name=team_name)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created team: {team_name}')
                )
        else:
            try:
                team = Team.objects.get(name=team_name)
            except Team.DoesNotExist:
                raise CommandError(
                    f'Team "{team_name}" does not exist. '
                    f'Use --create-team to create it.'
                )

        # Create API key
        api_key = ApiKey.objects.create(
            team=team,
            name=key_name
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nAPI Key created successfully!\n'
                f'Team: {team.name}\n'
                f'Name: {api_key.name}\n'
                f'Key: {api_key.key}\n'
                f'\nIMPORTANT: Save this key securely. '
                f'It cannot be retrieved again.\n'
            )
        )
