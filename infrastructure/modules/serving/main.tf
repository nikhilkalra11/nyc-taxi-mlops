data "aws_availability_zones" "available" { state = "available" }
locals {
  prefix = "${var.name}-${var.environment}"
  image  = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
}
resource "aws_ecr_repository" "api" {
  name                 = "${local.prefix}-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "AES256"
  }
  force_delete = false
}
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy     = jsonencode({ rules = [{ rulePriority = 1, description = "Keep last 15 images", selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 15 }, action = { type = "expire" } }] })
}
resource "aws_vpc" "serving" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.prefix}-vpc" }
}
resource "aws_internet_gateway" "serving" {
  vpc_id = aws_vpc.serving.id
  tags   = { Name = "${local.prefix}-igw" }
}
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.serving.id
  cidr_block              = cidrsubnet(aws_vpc.serving.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.prefix}-public-${count.index}" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.serving.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.serving.id
  }
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "alb" {
  name_prefix = "${local.prefix}-alb-"
  description = "Public HTTP access to dev ALB"
  vpc_id      = aws_vpc.serving.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  lifecycle { create_before_destroy = true }
}
resource "aws_security_group" "task" {
  name_prefix = "${local.prefix}-task-"
  description = "Only ALB can access application"
  vpc_id      = aws_vpc.serving.id
  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  lifecycle { create_before_destroy = true }
}
resource "aws_lb" "api" {
  name               = substr("${local.prefix}-alb", 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}
resource "aws_lb_target_group" "api" {
  name        = substr("${local.prefix}-tg", 0, 32)
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.serving.id
  health_check {
    path                = "/health/ready"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.prefix}-api"
  retention_in_days = 7
}
resource "aws_iam_role" "execution" {
  name               = "${local.prefix}-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role" "task" {
  name               = "${local.prefix}-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "models" {
  name   = "read-model-artifacts"
  role   = aws_iam_role.task.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["s3:GetObject"], Resource = "arn:aws:s3:::${var.data_bucket}/${trim(var.model_prefix, "/")}/*" }] })
}
resource "aws_ecs_cluster" "api" { name = "${local.prefix}-cluster" }
resource "aws_ecs_task_definition" "api" {
  family                   = "${local.prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }
  container_definitions = jsonencode([{
    name         = "api", image = local.image, essential = true,
    portMappings = [{ containerPort = var.container_port, hostPort = var.container_port, protocol = "tcp" }],
    environment = [
      { name = "MODEL_BUCKET", value = var.data_bucket },
      { name = "MODEL_PREFIX", value = var.model_prefix },
      { name = "AWS_REGION", value = var.region },
      { name = "LOG_LEVEL", value = "INFO" }
    ],
    logConfiguration       = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.api.name, "awslogs-region" = var.region, "awslogs-stream-prefix" = "api" } },
    readonlyRootFilesystem = false
  }])
}
resource "aws_ecs_service" "api" {
  count                              = var.enable_service ? 1 : 0
  name                               = "${local.prefix}-service"
  cluster                            = aws_ecs_cluster.api.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.desired_count
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 120
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.container_port
  }
  depends_on = [aws_lb_listener.http, aws_iam_role_policy_attachment.execution]
}
