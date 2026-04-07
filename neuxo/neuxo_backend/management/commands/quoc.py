from django.core.management.base import BaseCommand

from neuxo_backend.crawler.LinkedinJobServices import LinkedinJobService


class Command(BaseCommand):
    help = "This is a placeholder command."

    def handle(self, *args, **options):
        self.stdout.write("Placeholder command executed successfully.")
        # data = Linkedin().run_get_posts_and_upsert_mentions_by_urls(['https://linkedin.com/in/benedick-beeson-b6aa9531','https://cn.linkedin.com/in/hongfeng-zheng-93975818','https://linkedin.com/in/thuria-wenbar-98a435127','https://cn.linkedin.com/in/%E6%9C%B1%E7%BB%B4%E7%8E%AE-caroline-zhu-87218b59','http://www.variflight.com' , 'https://evaro.com'])
        # data = LinkedinProfileService().run_get_profile_person_by_query([
        #     "https://vn.linkedin.com/in/stephen-t-b30353222",
        #     "https://ke.linkedin.com/in/george-kimunguyi-26911413b",
        #     "https://sg.linkedin.com/in/wei-na-tan-58169a84",
        #     "https://sg.linkedin.com/in/steven-bong-2042881a",
        #     "https://sg.linkedin.com/in/jacky-lee-22062169"
        # ])
        data = LinkedinJobService().run_get_jobs_and_upsert_by_company_names(
            ["listed-fans"]
        )
        print("data :", data)
