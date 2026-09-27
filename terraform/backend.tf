terraform {
  backend "s3" {
    bucket         = "mays-orders-tfstate-central-240571105849"
    key            = "terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "mays-orders-terraform-locks"
    encrypt        = true
    workspace_key_prefix = "env:"
  }
}
