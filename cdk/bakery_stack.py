import os

from aws_cdk import (
    aws_ec2,
    aws_ecs,
    aws_ecs_patterns,
    aws_iam,
    aws_secretsmanager,
    core,
)


class BakeryStack(core.Stack):
    def __init__(
        self, scope: core.Construct, construct_id: str, identifier: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = aws_ec2.Vpc(
            self,
            id=f"bakery-vpc-{identifier}",
            cidr="10.0.0.0/16",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            nat_gateways=0,
            subnet_configuration=[
                aws_ec2.SubnetConfiguration(
                    name="PublicSubnet1", subnet_type=aws_ec2.SubnetType.PUBLIC
                )
            ],
            max_azs=3,
        )

        cluster = aws_ecs.Cluster(self, id=f"bakery-cluster-{identifier}", vpc=vpc)

        prefect_ecs_agent_task_definition = aws_ecs.FargateTaskDefinition(
            self,
            id=f"prefect-ecs-agent-task-definition-{identifier}",
            cpu=512,
            memory_limit_mib=2048,
        )

        runner_token_secret = aws_ecs.Secret.from_secrets_manager(
            secret=aws_secretsmanager.Secret.from_secret_arn(
                self,
                id=f"prefect-cloud-runner-token-{identifier}",
                secret_arn=os.environ["RUNNER_TOKEN_SECRET_ARN"],
            ),
            field="RUNNER_TOKEN",
        )

        prefect_ecs_agent_task_definition.add_container(
            id=f"prefect-ecs-agent-task-container-{identifier}",
            image=aws_ecs.ContainerImage.from_asset(directory="cdk/agent"),
            port_mappings=[aws_ecs.PortMapping(container_port=8080, host_port=8080)],
            logging=aws_ecs.LogDriver.aws_logs(stream_prefix="ecs-agent"),
            secrets={"PREFECT__CLOUD__AGENT__AUTH_TOKEN": runner_token_secret},
        )

        prefect_ecs_agent_service = (
            aws_ecs_patterns.ApplicationLoadBalancedFargateService(
                self,
                id=f"prefect-ecs-agent-service-{identifier}",
                assign_public_ip=True,
                platform_version=aws_ecs.FargatePlatformVersion.LATEST,
                desired_count=1,
                task_definition=prefect_ecs_agent_task_definition,
                cluster=cluster,
                propagate_tags=aws_ecs.PropagatedTagSource.SERVICE,
            )
        )

        prefect_ecs_agent_service.target_group.configure_health_check(
            path="/api/health", port="8080"
        )
