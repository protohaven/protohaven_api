import asana
from config import get_config

cfg = get_config()['asana']

client = asana.Client.access_token(cfg['token'])

def get_all_projects():
  return client.projects.get_projects_for_workspace(cfg['gid'], {}, opt_pretty=True)

def get_tech_tasks():
  #https://developers.asana.com/reference/gettasksforproject
  return client.tasks.get_tasks_for_project(cfg['techs_project'], {
        "opt_fields": ["completed", "custom_fields.name", "custom_fields.number_value", "custom_fields.text_value"],
        "limit": 10, # TODO remove
      }, opt_pretty=True)

# TODO create tech task for maintenance

if __name__ == "__main__":
    #for project in get_all_projects():
    #    print(project)
    for task in get_tech_tasks():
        print(task)
